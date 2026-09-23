import Foundation
import Observation

@MainActor @Observable
final class ConversationStore {
    private(set) var threads: [ThreadSummary] = []
    private(set) var answerers: [Answerer] = []
    private(set) var current: ChatThread?
    private(set) var selectedID: String?
    private(set) var loading = false
    private(set) var busy = false
    private(set) var errorMessage: String?
    private(set) var searchPage: ThreadSearchPage?
    private(set) var searching = false
    var answererID = ""
    var reasoningEffort = "none"
    var draft = ""
    var searchAnchor: String?
    private let api: any PlatformServing
    private var generation = 0
    private var selection = 0
    private var eventVersion = 0
    private var searchVersion = 0
    private var listVersion = 0
    private var preferencesKey = ""

    init(api: any PlatformServing) { self.api = api }
    var selectedAnswerer: Answerer? { answerers.first { $0.id == answererID } }
    var responding: Bool { current?.latest_response?.isActive == true }
    var canSend: Bool {
        !busy && !loading && !responding && selectedAnswerer != nil
            && draft.trimmingCharacters(in: .whitespacesAndNewlines).count > 0
            && draft.unicodeScalars.count <= 8000
    }

    func reset(identity: String, origin: URL) {
        generation += 1
        selection += 1
        searchVersion += 1
        listVersion += 1
        threads = []
        answerers = []
        current = nil
        selectedID = nil
        searchPage = nil
        errorMessage = nil
        draft = ""
        busy = false
        loading = false
        searching = false
        answererID = ""
        searchAnchor = nil
        preferencesKey = "chat.selected." + origin.absoluteString + "." + identity
    }
    func load() async {
        let version = generation
        do {
            let page: ItemPage<Answerer> = try await api.get("/answerers")
            guard version == generation else { return }
            answerers = page.items
            chooseAnswerer(page.items.first(where: { $0.is_default })?.id ?? page.items.first?.id ?? "")
            await refreshList()
            guard version == generation else { return }
            if let saved = UserDefaults.standard.string(forKey: preferencesKey),
                threads.contains(where: { $0.id == saved })
            {
                await select(saved)
            }
        } catch { if version == generation { errorMessage = error.localizedDescription } }
    }
    func chooseAnswerer(_ id: String) {
        answererID = id
        if let option = selectedAnswerer,
            !option.reasoning_efforts.contains(where: { $0.id == reasoningEffort })
        {
            reasoningEffort = option.default_reasoning_effort
        }
    }
    func newConversation() {
        selection += 1
        selectedID = nil
        current = nil
        draft = ""
        errorMessage = nil
        loading = false
        searchAnchor = nil
        UserDefaults.standard.removeObject(forKey: preferencesKey)
    }
    func select(_ id: String, entryID: String? = nil) async {
        selection += 1
        let version = selection
        selectedID = id
        current = nil
        draft = ""
        errorMessage = nil
        loading = true
        searchAnchor = entryID
        UserDefaults.standard.set(id, forKey: preferencesKey)
        await refreshCurrent()
        if selection == version {
            loading = false
            if let current {
                chooseAnswerer(current.answerer)
                if let response = current.latest_response { reasoningEffort = response.reasoning_effort }
                chooseAnswerer(answererID)
            }
        }
    }
    func refreshList() async {
        listVersion += 1
        let request = listVersion
        let version = generation
        do {
            let page: ItemPage<ThreadSummary> = try await api.get("/threads")
            guard generation == version, request == listVersion else { return }
            threads = page.items
        } catch {
            if generation == version, request == listVersion { errorMessage = error.localizedDescription }
        }
    }
    func refreshCurrent() async {
        guard let id = selectedID else { return }
        let version = generation
        let selected = selection
        let events = eventVersion
        do {
            let thread: ChatThread = try await api.get("/threads/" + id)
            guard version == generation, selected == selection else { return }
            if let current, thread.revision < current.revision { return }
            if events != eventVersion, let current, thread.revision <= current.revision { return }
            current = thread
            upsert(thread.summary)
            errorMessage = nil
        } catch {
            guard version == generation, selected == selection else { return }
            errorMessage = error.localizedDescription
            if (error as? PlatformError)?.status == 404 { current = nil }
        }
    }
    func send() async -> Bool {
        guard canSend else { return false }
        let content = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        let id = selectedID
        let version = generation
        let selected = selection
        let sentDraft = draft
        busy = true
        errorMessage = nil
        defer { if version == generation { busy = false } }
        do {
            var values: [String: Any] = [
                "input": content, "answerer": answererID, "reasoning_effort": reasoningEffort,
            ]
            if let id { values["thread_id"] = id }
            let result: ResponseCreation = try await api.call(
                id == nil ? "/threads" : "/response-requests", method: "POST", body: jsonBody(values))
            guard version == generation else { return false }
            upsert(result.thread.summary)
            if selection == selected {
                selectedID = result.thread.id
                if current == nil || result.thread.revision >= current!.revision {
                    current = result.thread
                    current?.latest_response = result.response
                }
                UserDefaults.standard.set(result.thread.id, forKey: preferencesKey)
                if draft == sentDraft { draft = "" }
            }
            return true
        } catch {
            if version == generation, selected == selection {
                errorMessage = error.localizedDescription
                // A timed-out POST may already be committed. Reconcile before allowing another send.
                if id != nil { await refreshCurrent() } else { await refreshList() }
                errorMessage = error.localizedDescription
            }
            return false
        }
    }
    func cancel() async {
        guard let execution = current?.latest_response?.execution, responding else { return }
        await mutateThread {
            try await self.api.call("/executions/" + execution.id + "/cancel", method: "POST")
        }
    }
    func regenerate() async {
        guard let response = current?.latest_response, ["completed", "cancelled"].contains(response.status)
        else { return }
        await mutateThread {
            let result: ResponseCreation = try await self.api.call(
                "/response-requests/" + response.id + "/regenerations", method: "POST")
            var thread = result.thread
            thread.latest_response = result.response
            return thread
        }
    }
    private func mutateThread(_ action: () async throws -> ChatThread) async {
        guard !busy else { return }
        let version = generation
        let selected = selection
        busy = true
        errorMessage = nil
        defer { if version == generation { busy = false } }
        do {
            let incoming = try await action()
            guard version == generation else { return }
            upsert(incoming.summary)
            if selected == selection, incoming.revision >= (current?.revision ?? -1) { current = incoming }
        } catch {
            if version == generation, selected == selection {
                await refreshCurrent()
                errorMessage = error.localizedDescription
            }
        }
    }
    func evaluate(_ entry: ChatEntry, value: String) async {
        guard !busy, let execution = entry.execution_id else { return }
        let version = generation
        let selected = selection
        busy = true
        defer { if version == generation { busy = false } }
        do {
            let clearing = entry.evaluation == value
            try await api.perform(
                "/executions/" + execution + "/evaluation", method: clearing ? "DELETE" : "PUT",
                body: clearing ? nil : jsonBody(["value": value]))
            if version == generation, selected == selection { await refreshCurrent() }
        } catch { if version == generation { errorMessage = "評価を保存できませんでした。" } }
    }
    func rename(_ id: String, title: String) async {
        let version = generation
        do {
            let summary: ThreadSummary = try await api.call(
                "/threads/" + id, method: "PATCH", body: jsonBody(["title": title]))
            guard version == generation else { return }
            upsert(summary)
            if selectedID == id { await refreshCurrent() }
        } catch { if version == generation { errorMessage = error.localizedDescription } }
    }
    func archive(_ id: String) async {
        let version = generation
        do {
            try await api.perform("/threads/" + id + "/archive", method: "POST")
            guard version == generation else { return }
            threads.removeAll { $0.id == id }
            if selectedID == id { newConversation() }
        } catch { if version == generation { errorMessage = error.localizedDescription } }
    }
    func search(_ query: String) async {
        searchVersion += 1
        let version = searchVersion
        let identity = generation
        searchPage = nil
        let query = String(query.trimmingCharacters(in: .whitespacesAndNewlines).prefix(100))
        guard !query.isEmpty else {
            searching = false
            return
        }
        searching = true
        defer { if version == searchVersion { searching = false } }
        do {
            try await Task.sleep(for: .milliseconds(300))
            try Task.checkCancellation()
            let result: ThreadSearchPage = try await api.call(
                "/thread-searches", method: "POST", body: jsonBody(["query": query, "limit": 20]))
            guard identity == generation, version == searchVersion, !Task.isCancelled else { return }
            searchPage = result
        } catch is CancellationError {} catch {
            if version == searchVersion { errorMessage = error.localizedDescription }
        }
    }
    /// Returns true when an authoritative HTTP snapshot is needed.
    func receive(_ event: RealtimeEvent) -> Bool {
        if event.type == "sync.required" { return true }
        guard event.thread_id == selectedID else { return false }
        eventVersion += 1
        if event.type == "thread.archived" {
            newConversation()
            return true
        }
        guard event.type.hasPrefix("response.") else { return true }
        guard event.type != "response.queued", var thread = current, var response = thread.latest_response,
            response.id == event.response_request_id, response.execution.id == event.execution_id
        else { return true }
        guard (event.thread_revision ?? 0) >= thread.revision else { return false }
        guard response.isActive else { return true }
        let terminal = ["response.completed", "response.failed", "response.cancelled"].contains(event.type)
        response.status = terminal ? String(event.type.dropFirst("response.".count)) : "running"
        response.execution.status = response.status
        if let content = event.data?.content { response.execution.partial_output = content }
        if let model = event.data?.resolved_model { response.execution.resolved_model = model }
        if let result = event.data?.result_entry_id { response.execution.result_entry_id = result }
        if let error = event.data?.error_code { response.execution.error_code = error }
        if terminal {
            response.execution.generation_phase = nil
        } else if event.type == "response.delta" || event.data?.phase == "answering" {
            response.execution.generation_phase = "answering"
        } else if response.execution.generation_phase == nil {
            response.execution.generation_phase = event.data?.phase
        }
        thread.revision = event.thread_revision ?? thread.revision
        thread.latest_response = response
        current = thread
        return terminal
    }
    private func upsert(_ summary: ThreadSummary) {
        if let old = threads.first(where: { $0.id == summary.id }), old.revision > summary.revision { return }
        threads.removeAll { $0.id == summary.id }
        threads.append(summary)
        threads.sort { $0.last_activity_at > $1.last_activity_at }
    }
}

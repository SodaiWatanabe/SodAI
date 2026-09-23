import Foundation
import Observation

@MainActor @Observable
final class BrainStore {
    private(set) var state: BrainState?
    private(set) var busy = false
    private(set) var loading = false
    private(set) var errorMessage: String?
    private(set) var history: [BrainAnswerSummary] = []
    private(set) var nextCursor: String?
    private(set) var historyLoading = false
    private(set) var detail: BrainAnswerDetail?
    private(set) var detailLoading = false
    private(set) var draft = ""
    private(set) var draftSaving = false
    private(set) var draftError: String?
    var conditions = BrainConditions.initial
    var visible = false
    private(set) var authenticated = false
    private(set) var needsValidation = false
    private var readVersion = 0
    private let api: any PlatformServing
    private var generation = 0
    private var stateVersion = 0
    private var historyVersion = 0
    private var detailVersion = 0
    private var revision = 0
    private var savedDraft = ""
    private var saveTask: Task<Void, Never>?
    private var debounce: Task<Void, Never>?
    private var autoSubmittedClaim: String?

    init(api: any PlatformServing) { self.api = api }
    var assignment: BrainAssignment? { state?.assignment }
    var assigned: Bool { assignment != nil }
    var deadlineExpired: Bool { assignment.map { $0.deadline <= Date() } ?? false }
    func requireValidation() { if assigned { needsValidation = true } }
    func reset(authenticated: Bool) {
        generation += 1
        stateVersion += 1
        historyVersion += 1
        detailVersion += 1
        self.authenticated = authenticated
        needsValidation = false
        state = nil
        history = []
        nextCursor = nil
        detail = nil
        errorMessage = nil
        busy = false
        loading = false
        historyLoading = false
        detailLoading = false
        conditions = .initial
        clearDraft()
    }
    private func clearDraft() {
        debounce?.cancel()
        saveTask?.cancel()
        debounce = nil
        saveTask = nil
        draft = ""
        savedDraft = ""
        revision = 0
        draftSaving = false
        draftError = nil
        autoSubmittedClaim = nil
    }
    private func apply(_ incoming: BrainState) {
        if incoming.assignment?.claim_id != assignment?.claim_id {
            clearDraft()
            detailVersion += 1
            detail = nil
            detailLoading = false
            if let assignment = incoming.assignment {
                draft = assignment.draft_content
                savedDraft = draft
                revision = assignment.draft_revision
            }
        } else if let assignment = incoming.assignment {
            // Accept edits made on another client only if there are no unsaved local edits.
            if assignment.draft_revision > revision, draft == savedDraft {
                draft = assignment.draft_content
                savedDraft = draft
            }
            revision = max(revision, assignment.draft_revision)
        }
        if state?.answer_conditions != incoming.answer_conditions { conditions = incoming.answer_conditions }
        state = incoming
    }
    func refresh() async {
        guard authenticated else { return }
        readVersion += 1
        let read = readVersion
        let version = generation
        let request = stateVersion
        loading = state == nil
        defer { if version == generation { loading = false } }
        do {
            let incoming: BrainState = try await api.get("/human/state")
            guard version == generation, request == stateVersion, read == readVersion else { return }
            apply(incoming)
            needsValidation = false
            errorMessage = nil
        } catch {
            if version == generation, request == stateVersion { errorMessage = error.localizedDescription }
        }
    }
    func toggleReadiness() async {
        if state?.status == "waiting" {
            _ = await mutate("/human/readiness", method: "DELETE")
        } else {
            _ = await mutate("/human/readiness", method: "PUT", body: try? JSONEncoder().encode(conditions))
        }
    }
    func heartbeat() async {
        guard authenticated, visible, !busy else { return }
        if state?.status == "waiting" || assigned {
            _ = await mutate(
                "/human/readiness", method: "PUT",
                body: try? JSONEncoder().encode(state?.answer_conditions ?? conditions))
        } else {
            await refresh()
        }
        if draft != savedDraft { await flushDraft() }
    }
    func release() async {
        guard let assignment, !deadlineExpired, !needsValidation else { return }
        _ = await mutate(
            "/human/claims/" + assignment.claim_id + (assignment.canSkip() ? "/skip" : "/decline"),
            method: "POST")
    }
    @discardableResult func answer() async -> Bool {
        guard let assignment, !busy, !needsValidation else { return false }
        let content = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty, content.unicodeScalars.count <= 32000, !deadlineExpired else { return false }
        // Answer includes the whole current text, independent of a draft request in flight.
        let success = await mutate(
            "/human/claims/" + assignment.claim_id + "/answer", method: "POST",
            body: try? jsonBody(["content": content]))
        if success { await refreshHistory() }
        return success
    }
    private func mutate(_ path: String, method: String, body: Data? = nil) async -> Bool {
        guard authenticated, !busy else { return false }
        stateVersion += 1
        let request = stateVersion
        let version = generation
        busy = true
        errorMessage = nil
        defer { if version == generation, request == stateVersion { busy = false } }
        do {
            let incoming: BrainState = try await api.call(path, method: method, body: body)
            guard version == generation, request == stateVersion else { return false }
            apply(incoming)
            return true
        } catch {
            guard version == generation, request == stateVersion else { return false }
            // A stale claim or an uncertain response must not retain private context indefinitely.
            if (error as? PlatformError)?.status == 404 { revokeAssignment() }
            await refresh()
            if version == generation { errorMessage = error.localizedDescription }
            return false
        }
    }
    func editDraft(_ content: String) {
        guard assigned, !deadlineExpired, !needsValidation else { return }
        draft = String(String.UnicodeScalarView(content.unicodeScalars.prefix(32000)))
        debounce?.cancel()
        debounce = Task { [weak self] in
            do { try await Task.sleep(for: .milliseconds(400)) } catch { return }
            self?.debounce = nil
            await self?.flushDraft()
        }
    }
    func flushDraft() async {
        debounce?.cancel()
        debounce = nil
        if let saveTask {
            await saveTask.value
            return
        }
        guard let claim = assignment?.claim_id, draft != savedDraft, !deadlineExpired else { return }
        let version = generation
        let task = Task { @MainActor [weak self] in
            guard let self else { return }
            self.draftSaving = true
            defer {
                if self.generation == version, self.assignment?.claim_id == claim {
                    self.draftSaving = false
                    self.saveTask = nil
                }
            }
            // Serial writes coalesce typing; revisions are allocated immediately before each request.
            while !Task.isCancelled, self.generation == version, self.assignment?.claim_id == claim,
                self.draft != self.savedDraft, !self.deadlineExpired
            {
                let content = self.draft
                self.revision += 1
                let sentRevision = self.revision
                do {
                    let result: DraftReceipt = try await self.api.call(
                        "/human/claims/" + claim + "/draft", method: "PUT",
                        body: jsonBody(["content": content, "revision": sentRevision]))
                    guard self.generation == version, self.assignment?.claim_id == claim, !Task.isCancelled
                    else { return }
                    self.revision = max(self.revision, result.revision)
                    if result.revision == sentRevision { self.savedDraft = content }
                    self.draftError = nil
                } catch {
                    guard self.generation == version, self.assignment?.claim_id == claim, !Task.isCancelled
                    else { return }
                    self.draftError = "下書きを保存できませんでした。接続を確認してください。"
                    if (error as? PlatformError)?.status == 404 {
                        self.revokeAssignment()
                        await self.refresh()
                    }
                    return
                }
            }
        }
        saveTask = task
        await task.value
    }
    func tick() async {
        guard visible, !needsValidation, let assignment else { return }
        let remaining = assignment.deadline.timeIntervalSinceNow
        if remaining <= 0.3, autoSubmittedClaim != assignment.claim_id, !busy {
            autoSubmittedClaim = assignment.claim_id
            if remaining > 0, !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                _ = await answer()
            }
            if self.assignment?.claim_id == assignment.claim_id, remaining <= 0 {
                await heartbeat()
            }
        } else if remaining <= 0, !busy {
            await refresh()
        }
    }
    private func revokeAssignment() {
        stateVersion += 1
        busy = false
        needsValidation = false
        state?.assignment = nil
        state?.status = "idle"
        detailVersion += 1
        detail = nil
        clearDraft()
    }
    func receive(_ event: RealtimeEvent) -> Bool {
        if event.type == "sync.required" { return true }
        if event.type == "human.assigned" {
            stateVersion += 1
            busy = false
            return true
        }
        guard ["human.assignment.cancelled", "human.answer.auto_submitted"].contains(event.type),
            event.data?.claim_id == assignment?.claim_id, assignment != nil
        else { return false }
        // Revoke private context synchronously, before any reconnect or HTTP await.
        revokeAssignment()
        return true
    }
    func refreshHistory(more: Bool = false) async {
        guard authenticated, !historyLoading else { return }
        guard !more || nextCursor != nil else { return }
        historyVersion += 1
        let request = historyVersion
        let version = generation
        historyLoading = true
        defer { if version == generation { historyLoading = false } }
        var components = URLComponents()
        components.queryItems = [URLQueryItem(name: "limit", value: "20")]
        if more { components.queryItems?.append(URLQueryItem(name: "cursor", value: nextCursor)) }
        do {
            let page: BrainAnswerPage = try await api.get(
                "/human/answers?" + (components.percentEncodedQuery ?? ""))
            guard version == generation, request == historyVersion else { return }
            if more {
                let ids = Set(history.map(\.id))
                history += page.items.filter { !ids.contains($0.id) }
            } else {
                history = page.items
            }
            nextCursor = page.next_cursor
        } catch { if version == generation { errorMessage = "回答履歴を読み込めませんでした。" } }
    }
    func openAnswer(_ id: String) async {
        guard !assigned, authenticated else { return }
        detailVersion += 1
        let request = detailVersion
        let version = generation
        detail = nil
        detailLoading = true
        errorMessage = nil
        defer { if request == detailVersion { detailLoading = false } }
        do {
            let answer: BrainAnswerDetail = try await api.get("/human/answers/" + id)
            guard version == generation, request == detailVersion, !assigned else { return }
            detail = answer
        } catch { if version == generation, request == detailVersion { errorMessage = "回答履歴を読み込めませんでした。" } }
    }
    func closeAnswer() {
        detailVersion += 1
        detail = nil
        detailLoading = false
    }
}

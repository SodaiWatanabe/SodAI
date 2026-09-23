import Foundation
import Testing

@testable import SodAI

@MainActor @Suite(.serialized)
struct PlatformTests {
    @Test func cumulativeDeltasCannotMixAttemptsOrRegressTerminalResponse() async throws {
        let api = ScriptedPlatformAPI()
        let store = ConversationStore(api: api)
        await store.select("t1")
        #expect(store.receive(try event("response.delta", content: "こん")) == false)
        #expect(store.receive(try event("response.delta", content: "こんにちは")) == false)
        #expect(store.current?.latest_response?.execution.partial_output == "こんにちは")
        #expect(store.receive(try event("response.delta", content: "old", execution: "old")))
        #expect(store.current?.latest_response?.execution.partial_output == "こんにちは")
        #expect(store.receive(try event("response.completed", content: "完成", revision: 3)))
        #expect(store.receive(try event("response.delta", content: "stale", revision: 2)) == false)
        #expect(store.current?.latest_response?.execution.partial_output == "完成")
        #expect(store.current?.latest_response?.status == "completed")
    }
    @Test func snapshotStartedBeforeDeltaDoesNotEraseStreamingText() async throws {
        let api = ScriptedPlatformAPI()
        let store = ConversationStore(api: api)
        await store.select("t1")
        let gate = ResponseGate()
        api.handler = { _, _, _ in await gate.wait() }
        let request = Task { await store.refreshCurrent() }
        await gate.untilWaiting()
        _ = store.receive(try event("response.delta", content: "最新"))
        gate.finish(Fixtures.thread())
        await request.value
        #expect(store.current?.latest_response?.execution.partial_output == "最新")
    }
    @Test func accountSwitchDiscardsOutstandingConversationAndSearchResponses() async {
        let api = ScriptedPlatformAPI()
        let store = ConversationStore(api: api)
        let gate = ResponseGate()
        api.handler = { _, _, _ in await gate.wait() }
        let request = Task { await store.select("t1") }
        await gate.untilWaiting()
        store.reset(identity: "different-user", origin: Fixtures.origin)
        gate.finish(Fixtures.thread())
        await request.value
        #expect(store.current == nil)
        #expect(store.threads.isEmpty)
        #expect(store.selectedID == nil)
    }
    @Test func sendPreservesDraftOnCreditFailureAndUsesChosenModel() async throws {
        let api = ScriptedPlatformAPI()
        let store = ConversationStore(api: api)
        await store.load()
        store.draft = "こんにちは"
        api.handler = { _, method, body in
            if method == "POST" {
                let values = try JSONSerialization.jsonObject(with: #require(body)) as! [String: String]
                #expect(values["answerer"] == "asuka-1.1")
                #expect(values["input"] == "こんにちは")
                throw PlatformError(status: 402)
            }
            return Fixtures.list
        }
        #expect(await store.send() == false)
        #expect(store.draft == "こんにちは")
        #expect(store.errorMessage?.contains("クレジット") == true)
        #expect(!store.busy)
    }
    @Test func foregroundRevalidationBlocksAnswerUntilClaimIsConfirmed() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        brain.editDraft("保留する回答")
        brain.requireValidation()
        let count = api.requests.count
        #expect(await brain.answer() == false)
        #expect(api.requests.count == count)
        api.brain = Fixtures.brain(status: "idle")
        await brain.refresh()
        #expect(brain.assignment == nil)
        #expect(!brain.needsValidation)
        #expect(brain.draft.isEmpty)
    }
    @Test func completedEntriesDoNotDuplicateExecutionPlaceholder() throws {
        let thread = try JSONDecoder().decode(
            ChatThread.self, from: Fixtures.thread(status: "completed", persisted: true))
        #expect(thread.displayEntries.count == 2)
        #expect(thread.displayEntries.last?.content == "完成")
    }
    @Test func draftWritesAreSerializedAndNewestTextWins() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        let gate = ResponseGate()
        var contents: [String] = []
        var revisions: [Int] = []
        api.handler = { _, _, body in
            let values = try JSONSerialization.jsonObject(with: #require(body)) as! [String: Any]
            contents.append(values["content"] as! String)
            revisions.append(values["revision"] as! Int)
            if contents.count == 1 { return await gate.wait() }
            return try jsonBody(["revision": values["revision"]!])
        }
        brain.editDraft("first")
        let save = Task { await brain.flushDraft() }
        await gate.untilWaiting()
        brain.editDraft("latest")
        #expect(contents == ["first"])
        gate.finish(try jsonBody(["revision": 1]))
        await save.value
        #expect(contents == ["first", "latest"])
        #expect(revisions == [1, 2])
        #expect(!brain.draftSaving)
        #expect(brain.draftError == nil)
    }
    @Test func cancelledClaimClearsPrivateContextBeforeHTTPAndIgnoresLateDraft() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        let gate = ResponseGate()
        api.handler = { _, _, _ in await gate.wait() }
        brain.editDraft("private draft")
        let save = Task { await brain.flushDraft() }
        await gate.untilWaiting()
        let cancelled = try JSONDecoder().decode(
            RealtimeEvent.self,
            from: jsonBody([
                "type": "human.assignment.cancelled",
                "data": ["claim_id": "c1", "reason": "requester_cancelled"],
            ]))
        #expect(brain.receive(cancelled))
        #expect(brain.assignment == nil)
        #expect(brain.draft.isEmpty)
        gate.finish(try jsonBody(["revision": 1]))
        await save.value
        #expect(brain.draft.isEmpty)
        #expect(!brain.draftSaving)
    }
    @Test func staleStateCannotResurrectCancelledClaim() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        let gate = ResponseGate()
        api.handler = { _, _, _ in await gate.wait() }
        let refresh = Task { await brain.refresh() }
        await gate.untilWaiting()
        _ = brain.receive(
            try JSONDecoder().decode(
                RealtimeEvent.self,
                from: jsonBody([
                    "type": "human.assignment.cancelled",
                    "data": ["claim_id": "c1", "reason": "assignment_expired"],
                ])))
        gate.finish(Fixtures.brain())
        await refresh.value
        #expect(brain.assignment == nil)
    }
    @Test func deadlineSubmitsCurrentTextOnlyOnce() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        brain.visible = true
        brain.editDraft("締切の回答")
        api.brain = Fixtures.brain(deadline: Date().addingTimeInterval(0.25))
        await brain.refresh()
        api.handler = { path, method, body in
            if path.hasSuffix("/answer") {
                #expect(method == "POST")
                let values = try JSONSerialization.jsonObject(with: #require(body)) as! [String: String]
                #expect(values["content"] == "締切の回答")
                return Fixtures.brain(status: "idle")
            }
            return Fixtures.answerPage
        }
        await brain.tick()
        await brain.tick()
        #expect(api.requests.filter { $0.path.hasSuffix("/answer") }.count == 1)
        #expect(brain.assignment == nil)
    }
    @Test func answerHistoryIsBlockedWhileAssignedAndPagesAreDeduplicated() async throws {
        let api = ScriptedPlatformAPI()
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        let count = api.requests.count
        await brain.openAnswer("answer-1")
        #expect(api.requests.count == count)
        await brain.refreshHistory()
        await brain.refreshHistory(more: true)
        #expect(brain.history.count == 1)
        #expect(api.requests.last?.path.contains("cursor=") == true)
    }
    @Test func conditionsRemainContiguousAndRespectModelEffortLimits() throws {
        let humans = try JSONDecoder().decode(ItemPage<Answerer>.self, from: Fixtures.humans).items
        let result = BrainConditionRange.clamp(
            .init(answerer_ids: humans.map(\.id), reasoning_efforts: ["high", "xhigh"]), answerers: humans)
        #expect(result.reasoning_efforts == ["low", "medium", "high"])
        #expect(result.answerer_ids == ["human-lite", "human-standard"])
    }
    @Test func idleRefreshDoesNotOverwriteUnsavedConditions() async {
        let api = ScriptedPlatformAPI()
        api.brain = Fixtures.brain(status: "idle")
        let brain = BrainStore(api: api)
        brain.reset(authenticated: true)
        await brain.refresh()
        brain.conditions.reasoning_efforts = ["low", "medium"]
        await brain.refresh()
        #expect(brain.conditions.reasoning_efforts == ["low", "medium"])
    }
    @Test func serverDatesAndCreditScaleMatchWebContract() {
        #expect(PlatformDate.parse("2026-09-22T12:34:56.123456Z") != nil)
        #expect(PlatformDate.parse("2026-09-22T12:34:56+00:00") != nil)
        #expect(creditText(1_500_000, scale: 1_000_000) == "1.5")
    }
    private func event(_ type: String, content: String, execution: String = "e1", revision: Int = 2) throws
        -> RealtimeEvent
    {
        try JSONDecoder().decode(
            RealtimeEvent.self,
            from: jsonBody([
                "type": type, "thread_id": "t1", "thread_revision": revision,
                "response_request_id": "r1", "execution_id": execution, "data": ["content": content],
            ]))
    }
}

@MainActor final class ResponseGate {
    private var continuation: CheckedContinuation<Data, Never>?
    func wait() async -> Data { await withCheckedContinuation { continuation = $0 } }
    func untilWaiting() async { while continuation == nil { await Task.yield() } }
    func finish(_ data: Data) {
        continuation?.resume(returning: data)
        continuation = nil
    }
}
@MainActor final class ScriptedPlatformAPI: PlatformServing {
    struct Request {
        let path: String
        let method: String
        let body: Data?
        let headers: [String: String]
    }
    var requests: [Request] = []
    var handler: ((String, String, Data?) async throws -> Data)?
    var thread = Fixtures.thread()
    var brain = Fixtures.brain()
    func request(_ path: String, method: String, body: Data?, headers: [String: String]) async throws -> Data
    {
        requests.append(.init(path: path, method: method, body: body, headers: headers))
        if let handler { return try await handler(path, method, body) }
        if path == "/answerers" { return Fixtures.catalog }
        if path == "/threads" { return Fixtures.list }
        if path.hasPrefix("/threads/") { return thread }
        if path == "/human/state" { return brain }
        if path.hasPrefix("/human/answers?") { return Fixtures.answerPage }
        throw PlatformError(status: 404)
    }
}
enum Fixtures {
    static let origin = URL(string: "https://native-test.example.test")!
    static let list = Data(#"{"items":[]}"#.utf8)
    static let catalog = Data(
        #"{"items":[{"id":"asuka-1.1","name":"Asuka 1.1","description":"AI","kind":"ai","is_default":true,"is_legacy":false,"pricing":{"kind":"metered","scale":1000000,"maximum_charge":100},"reasoning_efforts":[{"id":"none","name":"なし","execution_time_limit_seconds":null,"customer_charge":100,"performer_reward":0}],"default_reasoning_effort":"none"}]}"#
            .utf8)
    static let humans = Data(
        #"{"items":[{"id":"human-lite","name":"Human Lite","description":"","kind":"human","is_default":false,"is_legacy":false,"pricing":{"kind":"metered","scale":1000000,"maximum_charge":100},"reasoning_efforts":[{"id":"low","name":"軽い","execution_time_limit_seconds":180,"customer_charge":100,"performer_reward":60}],"default_reasoning_effort":"low"},{"id":"human-standard","name":"Human Standard","description":"","kind":"human","is_default":false,"is_legacy":false,"pricing":{"kind":"metered","scale":1000000,"maximum_charge":100},"reasoning_efforts":[{"id":"low","name":"軽い","execution_time_limit_seconds":180,"customer_charge":100,"performer_reward":60},{"id":"high","name":"深い","execution_time_limit_seconds":1200,"customer_charge":1000,"performer_reward":600}],"default_reasoning_effort":"low"}]}"#
            .utf8)
    static func thread(status: String = "running", persisted: Bool = false) -> Data {
        Data(
            """
            {"id":"t1","title":"テストの会話","answerer":"asuka-1.1","revision":2,"last_activity_at":"2026-09-22T00:00:00Z",
            "entries":[{"id":"input1","author":{"id":"u1","kind":"human","name":"Tester"},"content":"こんにちは","ordinal":0}
            \(persisted ? #",{"id":"result1","author":{"id":"model1","kind":"model","name":"Asuka 1.1"},"content":"完成","ordinal":1,"execution_id":"e1","response_status":"completed"}"# : "")],
            "latest_response":{"id":"r1","requested_answerer":"asuka-1.1","reasoning_effort":"none","target_actor":{"id":"model1","kind":"model","name":"Asuka 1.1"},"status":"\(status)","execution":{"id":"e1","result_entry_id":\(persisted ? "\"result1\"" : "null"),"status":"\(status)","partial_output":"","generation_phase":"answering"}}}
            """.utf8)
    }
    static func brain(status: String = "assigned", deadline: Date = Date().addingTimeInterval(180)) -> Data {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let deadline = formatter.string(from: deadline)
        let assignment =
            """
            {"claim_id":"c1","answerer_name":"Human Lite","reasoning_effort":"low","skip_allowed_until":"2099-01-01T00:00:00Z","deadline_at":"\(deadline)","draft_content":"","draft_revision":0,"context":[{"author_kind":"human","content":"private context"}]}
            """
        return Data(
            """
            {"status":"\(status)","rank_name":"Human Lite","answer_conditions":{"answerer_ids":["human-lite"],"reasoning_efforts":["low"]},"available_answerer_ids":["human-lite"],"assignment":
            \(status == "assigned" ? assignment : "null")}
            """.utf8)
    }
    static let answerPage = Data(
        #"{"items":[{"execution_id":"answer-1","answerer_name":"Human Lite","reasoning_effort":"low","prompt_preview":"test","answered_at":"2026-09-22T00:00:00Z"}],"next_cursor":"opaque+/cursor="}"#
            .utf8)
}

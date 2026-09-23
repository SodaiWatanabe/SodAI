#if DEBUG
    import Foundation

    /// Local, in-process UI fixture. Selected only by -platform-ui-fixture, never by a server response.
    /// It uses a separate identity and no network or production Keychain access.
    @MainActor final class UITestFixture: PlatformServing, AuthServing, CredentialStoring {
        let origin = URL(string: "https://native-ui.example.test")!
        private var credential: SessionCredential? = .init(
            token: "local-ui-fixture", expiresAt: "2099-01-01T00:00:00Z",
            user: .init(id: "native-ui-fixture", name: "画面テスト", email: "native-ui@example.test"))
        private var messages: [[String: Any]] = []
        private var title = ""
        private var selectedAnswerer = "asuka-1.1"
        private var selectedEffort = "none"
        private var status = "idle"
        private var claim = "fixture-claim"
        private var draft = ""
        private var revision = 0
        private var answer: String?
        private let deadlineAt = ISO8601DateFormatter().string(from: Date().addingTimeInterval(180))
        private let scenario: String
        init(scenario: String) { self.scenario = scenario }
        func load() throws -> SessionCredential? { credential }
        func save(_ value: SessionCredential) throws { credential = value }
        func clear() throws { credential = nil }
        func capabilities() async throws -> AuthCapabilities { .init(google: false, mobile: false) }
        func exchange(code: String, attempt: OAuthAttempt) async throws -> SessionCredential {
            throw AuthFailure.unavailable
        }
        func restore(token: String) async throws -> SessionCredential {
            guard let credential else { throw AuthFailure.unauthenticated }
            return credential
        }
        func accessToken(sessionToken: String) async throws -> String { "fixture-only" }
        func signOut(token: String) async throws { credential = nil }
        func request(_ path: String, method: String, body: Data?, headers: [String: String]) async throws
            -> Data
        {
            if scenario == "operation-errors",
                (method == "POST" && ["/threads", "/response-requests"].contains(path))
                    || (method == "PUT" && path == "/human/readiness")
            {
                throw NSError(
                    domain: NSURLErrorDomain, code: NSURLErrorCancelled,
                    userInfo: [NSLocalizedDescriptionKey: "キャンセルしました"])
            }
            let values =
                (body.flatMap { try? JSONSerialization.jsonObject(with: $0) }) as? [String: Any] ?? [:]
            if path == "/answerers" {
                var models = [
                    model("asuka-1.1", name: "Asuka 1.1", human: false),
                    model("human-lite", name: "Human Lite", human: true),
                ]
                if scenario == "models" {
                    models += [
                        model("human-standard", name: "Human Standard", human: true),
                        model("human-pro", name: "Human Pro", human: true),
                        model("hina", name: "Hina", human: false, legacy: true),
                    ]
                }
                return try jsonBody(["items": models])
            }
            if path == "/credits" {
                return try jsonBody([
                    "scale": 1_000_000, "available": 12_000_000, "reserved": 0, "free_allowance": NSNull(),
                ])
            }
            if path == "/threads", method == "GET" {
                if scenario == "sidebar" {
                    return try jsonBody([
                        "items": (1...30).map { index in
                            summary.merging([
                                "id": "sidebar-thread-\(index)",
                                "title": index == 1
                                    ? "1. 週末の予定を一緒に考える：家族とのお出かけや買い物、読書の時間について"
                                    : "\(index). 週末の予定を一緒に考える",
                            ]) { _, new in new }
                        }
                    ])
                }
                return try jsonBody(["items": title.isEmpty ? [] : [summary]])
            }
            if path == "/threads" || path == "/response-requests" {
                let text = values["input"] as? String ?? ""
                selectedAnswerer = values["answerer"] as? String ?? selectedAnswerer
                selectedEffort = values["reasoning_effort"] as? String ?? selectedEffort
                if title.isEmpty { title = text }
                let reply =
                    scenario == "models"
                    ? "\(selectedAnswerer)（\(effortName(selectedEffort))）の回答です。"
                    : "接続テストの回答です。Web版と同じ会話の流れを確認できます。"
                messages += [entry(text, human: true), entry(reply, human: false)]
                return try jsonBody(["thread": thread, "response": response])
            }
            if path == "/thread-searches" {
                let match =
                    !title.isEmpty
                    && (title.contains(values["query"] as? String ?? "")
                        || messages.contains {
                            ($0["content"] as? String ?? "").contains(values["query"] as? String ?? "")
                        })
                return try jsonBody([
                    "items": match
                        ? [["thread": summary, "source": "title", "snippet": title, "entry_id": NSNull()]]
                        : [], "has_more": false,
                ])
            }
            if path.hasSuffix("/archive") {
                title = ""
                messages = []
                return Data()
            }
            if path.hasPrefix("/threads/sidebar-thread-") {
                let entries = [
                    entry("週末の予定を一緒に考えてください。", human: true)
                        .merging(["id": path + "/question"]) { _, new in new },
                    entry(String(repeating: "予定を詰め込みすぎず、休憩の時間も取りましょう。\n\n", count: 40), human: false)
                        .merging(["id": path + "/answer"]) { _, new in new },
                ]
                return try jsonBody(
                    summary.merging([
                        "id": String(path.split(separator: "/").last!),
                        "title": "週末の予定を一緒に考える", "entries": entries,
                        "latest_response": response,
                    ]) { _, new in new })
            }
            if path.hasPrefix("/threads/") {
                if method == "PATCH" {
                    title = values["title"] as? String ?? title
                    return try jsonBody(summary)
                }
                return try jsonBody(thread)
            }
            if path == "/human/state" { return try jsonBody(brainState) }
            if path == "/human/readiness" {
                status = method == "DELETE" ? "idle" : (scenario == "waiting" ? "waiting" : "assigned")
                return try jsonBody(brainState)
            }
            if path.hasSuffix("/draft") {
                draft = values["content"] as? String ?? ""
                revision = values["revision"] as? Int ?? revision
                return try jsonBody(["revision": revision])
            }
            if path.hasSuffix("/answer") {
                answer = values["content"] as? String
                status = "idle"
                draft = ""
                return try jsonBody(brainState)
            }
            if path.hasSuffix("/skip") || path.hasSuffix("/decline") {
                status = "waiting"
                draft = ""
                return try jsonBody(brainState)
            }
            if path.hasPrefix("/human/answers?") {
                return try jsonBody([
                    "items": answer == nil
                        ? []
                        : [
                            [
                                "execution_id": "fixture-answer", "answerer_name": "Human Lite",
                                "reasoning_effort": "low", "prompt_preview": "朝の挨拶を教えてください。",
                                "answered_at": "2026-09-22T00:00:00Z",
                            ]
                        ], "next_cursor": NSNull(),
                ])
            }
            if path.hasPrefix("/human/answers/") {
                return try jsonBody([
                    "execution_id": "fixture-answer", "answerer_name": "Human Lite",
                    "reasoning_effort": "low", "answered_at": "2026-09-22T00:00:00Z", "context": context,
                    "answer": answer ?? "",
                ])
            }
            if path.contains("/evaluation") { return Data("{}".utf8) }
            throw PlatformError(status: 404)
        }
        private var summary: [String: Any] {
            [
                "id": "fixture-thread", "title": title, "answerer": selectedAnswerer,
                "revision": messages.count, "last_activity_at": "2026-09-22T00:00:00Z",
            ]
        }
        private var thread: [String: Any] {
            summary.merging(["entries": messages, "latest_response": response]) { _, new in new }
        }
        private var response: [String: Any] {
            [
                "id": "fixture-response", "requested_answerer": selectedAnswerer,
                "reasoning_effort": selectedEffort, "target_actor": actor(false), "status": "completed",
                "execution": [
                    "id": "fixture-execution", "result_entry_id": messages.last?["id"] ?? "",
                    "status": "completed", "partial_output": "",
                ],
            ]
        }
        private func actor(_ human: Bool) -> [String: Any] {
            [
                "id": human ? "fixture-user" : "fixture-model", "kind": human ? "human" : "model",
                "name": human ? "Tester" : "Asuka 1.1",
            ]
        }
        private func entry(_ text: String, human: Bool) -> [String: Any] {
            [
                "id": UUID().uuidString, "author": actor(human), "content": text,
                "ordinal": messages.count + (human ? 0 : 1),
                "execution_id": human ? NSNull() : "fixture-execution", "response_status": "completed",
            ]
        }
        private func model(_ id: String, name: String, human: Bool, legacy: Bool = false) -> [String: Any] {
            let descriptions = [
                "asuka-1.1": "会話に最適。", "hina": "知能の萌芽を捉える。",
                "human-lite": "日常のやりとりに最適。", "human-standard": "幅広い相談に対応。", "human-pro": "より高度な応答。",
            ]
            let efforts = human ? (id == "human-lite" ? ["low"] : ["low", "medium", "high"]) : ["none"]
            return [
                "id": id, "name": name, "description": descriptions[id] ?? "", "kind": human ? "human" : "ai",
                "is_default": !human && !legacy, "is_legacy": legacy,
                "pricing": ["kind": "metered", "scale": 1_000_000, "maximum_charge": 1_000_000],
                "default_reasoning_effort": human ? (id == "human-lite" ? "low" : "medium") : "none",
                "reasoning_efforts": efforts.map { effort in
                    [
                        "id": effort, "name": effortName(effort),
                        "execution_time_limit_seconds": human ? (180 as Any) : NSNull(),
                        "customer_charge": 1_000_000, "performer_reward": 600000,
                    ]
                },
            ]
        }
        private var context: [[String: Any]] { [["author_kind": "human", "content": "朝の挨拶を教えてください。"]] }
        private var brainState: [String: Any] {
            [
                "status": status, "rank_name": "Human Lite",
                "answer_conditions": ["answerer_ids": ["human-lite"], "reasoning_efforts": ["low"]],
                "available_answerer_ids": ["human-lite"],
                "assignment": status == "assigned"
                    ? [
                        "claim_id": claim, "answerer_name": "Human Lite", "reasoning_effort": "low",
                        "skip_allowed_until": "2026-01-01T00:00:00Z", "deadline_at": deadlineAt,
                        "draft_content": draft, "draft_revision": revision, "context": context,
                    ] : NSNull(),
            ]
        }
    }
#endif

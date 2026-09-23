import Foundation
import Testing

@testable import SodAI

/// Explicit opt-in: uses the already signed-in device, generates one real AI answer,
/// and archives only the conversation created by this test. Never joins the Brain queue.
@MainActor
@Suite(.serialized, .enabled(if: ProcessInfo.processInfo.environment["SODAI_LIVE_INTEGRATION"] == "1"))
struct LivePlatformTests {
    @Test func productionAIStreamsAndConversationSurvivesNewClient() async throws {
        let origin = URL(string: "https://app.sodai.me")!
        let auth = AuthStore(
            client: AuthClient(origin: origin), storage: KeychainCredentialStore(origin: origin))
        await auth.restore()
        _ = try #require(auth.user, "実機でGoogleログインを先に完了してください。")
        let api = PlatformClient(origin: origin, auth: auth)
        let catalog: ItemPage<Answerer> = try await api.get("/answerers")
        let answerer = try #require(catalog.items.first { $0.is_default && $0.kind == "ai" })
        let connection = RealtimeConnection(api: api, origin: origin)
        var deltas: [RealtimeEvent] = []
        connection.start { event in if event.type == "response.delta" { deltas.append(event) } }
        defer { connection.stop() }
        let connectDeadline = Date().addingTimeInterval(15)
        while !connection.connected, Date() < connectDeadline {
            try await Task.sleep(for: .milliseconds(200))
        }
        #expect(connection.connected)
        let marker = "iOS接続検証-" + String(UUID().uuidString.prefix(8))
        let created: ResponseCreation = try await api.call(
            "/threads", method: "POST",
            body: jsonBody([
                "input": marker + "。日本語で短い挨拶を一文だけ返してください。",
                "answerer": answerer.id, "reasoning_effort": answerer.default_reasoning_effort,
            ]))
        var failure: Error?
        do {
            var thread = created.thread
            let deadline = Date().addingTimeInterval(100)
            while thread.latest_response?.isActive == true, Date() < deadline {
                try await Task.sleep(for: .seconds(2))
                thread = try await api.get("/threads/" + created.thread.id)
            }
            #expect(thread.latest_response?.status == "completed")
            #expect(thread.entries.count == 2)
            #expect(thread.entries.last?.content.isEmpty == false)
            #expect(deltas.contains { $0.thread_id == created.thread.id })
            let secondAuth = AuthStore(
                client: AuthClient(origin: origin), storage: KeychainCredentialStore(origin: origin))
            await secondAuth.restore()
            let second = PlatformClient(origin: origin, auth: secondAuth)
            let restored: ChatThread = try await second.get("/threads/" + thread.id)
            #expect(restored.entries.map(\.content) == thread.entries.map(\.content))
            let search: ThreadSearchPage = try await second.call(
                "/thread-searches", method: "POST", body: jsonBody(["query": marker, "limit": 20]))
            #expect(search.items.contains { $0.thread.id == thread.id })
            let state: BrainState = try await second.get("/human/state")
            #expect(!state.available_answerer_ids.isEmpty)
            let _: BrainAnswerPage = try await second.get("/human/answers?limit=20")
            let _: CreditBalance = try await second.get("/credits")
        } catch { failure = error }
        try await api.perform("/threads/" + created.thread.id + "/archive", method: "POST")
        if let failure { throw failure }
    }
}

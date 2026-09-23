import Foundation
import Testing

@testable import SodAI

@MainActor @Suite(.serialized)
struct PlatformTransportTests {
    private func session() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [PlatformURLProtocol.self]
        return URLSession(configuration: config)
    }
    @Test func concurrentGuestBootstrapAndNewClientKeepOneServerIdentity() async throws {
        let origin = URL(string: "https://" + UUID().uuidString + ".example.test")!
        let auth = TransportAuth()
        auth.saved = nil
        let store = AuthStore(client: auth, storage: auth)
        await store.restore()
        PlatformURLProtocol.router.reset(status: 200, cookie: "guest-token-for-test")
        let client = PlatformClient(origin: origin, auth: store, session: session())
        async let first: ItemPage<ThreadSummary> = client.get("/threads")
        async let second: ItemPage<ThreadSummary> = client.get("/threads")
        _ = try await (first, second)
        let nextClient = PlatformClient(origin: origin, auth: store, session: session())
        let _: ItemPage<ThreadSummary> = try await nextClient.get("/threads")
        let requests = PlatformURLProtocol.router.requests
        #expect(requests.filter { $0.url?.path.hasSuffix("answerers") == true }.count == 1)
        #expect(
            requests.filter { $0.url?.path.hasSuffix("threads") == true }.allSatisfy {
                $0.value(forHTTPHeaderField: "Cookie") == "sodai_guest=guest-token-for-test"
            })
        #expect(requests.allSatisfy { $0.value(forHTTPHeaderField: "Authorization") == nil })
    }
    @Test func authenticatedCallsUseShortJWTAndNeverRetryMutationAsGuest() async throws {
        let auth = TransportAuth()
        let store = AuthStore(client: auth, storage: auth)
        await store.restore()
        PlatformURLProtocol.router.reset(status: 401, cookie: nil)
        let client = PlatformClient(origin: auth.origin, auth: store, session: session())
        do {
            try await client.perform("/threads", method: "POST", body: jsonBody(["input": "test"]))
            Issue.record("Invalid JWT should fail")
        } catch { #expect((error as? PlatformError)?.status == 401) }
        let requests = PlatformURLProtocol.router.requests
        #expect(requests.count == 1)
        #expect(requests[0].value(forHTTPHeaderField: "Authorization") == "Bearer short-lived-jwt")
        #expect(requests[0].value(forHTTPHeaderField: "Cookie") == nil)
        #expect(requests[0].value(forHTTPHeaderField: "Origin") == auth.origin.absoluteString)
        #expect(requests[0].value(forHTTPHeaderField: "Content-Type") == "application/json")
        #expect(requests[0].httpMethod == "POST")
        #expect(auth.tokenRequests == 1)
    }
}
private final class PlatformURLProtocol: URLProtocol, @unchecked Sendable {
    static let router = TransportRouter()
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let (status, cookie) = Self.router.receive(request)
        var headers = ["Content-Type": "application/json"]
        if let cookie, request.url?.path.hasSuffix("answerers") == true {
            headers["Set-Cookie"] = "sodai_guest=" + cookie + "; Path=/; Max-Age=7776000; Secure; HttpOnly"
        }
        let response = HTTPURLResponse(
            url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(#"{"items":[]}"#.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
private final class TransportRouter: @unchecked Sendable {
    private let lock = NSLock()
    private var captured: [URLRequest] = []
    private var status = 200
    private var cookie: String?
    var requests: [URLRequest] { lock.withLock { captured } }
    func reset(status: Int, cookie: String?) {
        lock.withLock {
            captured = []
            self.status = status
            self.cookie = cookie
        }
    }
    func receive(_ request: URLRequest) -> (Int, String?) {
        lock.withLock {
            captured.append(request)
            return (status, cookie)
        }
    }
}
@MainActor private final class TransportAuth: AuthServing, CredentialStoring {
    let origin = URL(string: "https://transport.example.test")!
    var saved: SessionCredential? = .init(
        token: "long-lived-native-session", expiresAt: "2099-01-01T00:00:00Z",
        user: .init(id: "test-user", name: "Test", email: "test@example.test"))
    var tokenRequests = 0
    func load() throws -> SessionCredential? { saved }
    func save(_ value: SessionCredential) throws { saved = value }
    func clear() throws { saved = nil }
    func capabilities() async throws -> AuthCapabilities { .init(google: true, mobile: true) }
    func exchange(code: String, attempt: OAuthAttempt) async throws -> SessionCredential { saved! }
    func restore(token: String) async throws -> SessionCredential { saved! }
    func accessToken(sessionToken: String) async throws -> String {
        tokenRequests += 1
        return "short-lived-jwt"
    }
    func signOut(token: String) async throws {}
}

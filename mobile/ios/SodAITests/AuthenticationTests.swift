import Foundation
import Testing

@testable import SodAI

@MainActor
struct AuthenticationTests {
    private func callback(_ attempt: OAuthAttempt, state: String? = nil) -> URL {
        URL(
            string: "me.sodai.app://auth/callback?code=" + String(repeating: "a", count: 43) + "&state="
                + (state ?? attempt.state))!
    }

    private func successfulCallback(for authorization: URL) -> URL {
        let state = URLComponents(url: authorization, resolvingAgainstBaseURL: false)!
            .queryItems!.first { $0.name == "state" }!.value!
        return URL(
            string: "me.sodai.app://auth/callback?code=" + String(repeating: "a", count: 43) + "&state="
                + state)!
    }

    @Test func callbackRequiresExactDestinationStateAndFreshAttempt() throws {
        let attempt = try OAuthAttempt()
        #expect(try attempt.code(from: callback(attempt)).count == 43)
        #expect(throws: AuthFailure.invalidCallback(.stateMismatch)) {
            try attempt.code(from: callback(attempt, state: "wrong"))
        }
        #expect(throws: AuthFailure.invalidCallback(.stateCount)) {
            try attempt.code(from: URL(string: callback(attempt).absoluteString + "&state=" + attempt.state)!)
        }
        #expect(throws: AuthFailure.invalidCallback(.host)) {
            try attempt.code(
                from: URL(
                    string: callback(attempt).absoluteString.replacingOccurrences(
                        of: "//auth/", with: "//evil/"))!)
        }
        #expect(throws: AuthFailure.expiredAttempt) {
            try attempt.code(from: callback(attempt), now: attempt.createdAt.addingTimeInterval(601))
        }
        #expect(attempt.state != attempt.verifier)
        #expect(attempt.challenge.count == 43)
        #expect(
            try !attempt.authorizationURL(origin: URL(string: "https://app.sodai.me")!).absoluteString
                .contains(attempt.verifier))
    }

    @Test func serverCallbackQueryOrderAndBase64URLCharactersAreAccepted() throws {
        let attempt = try OAuthAttempt()
        // Server emits state before code and uses unpadded base64url.
        let code = "Ab9_-" + String(repeating: "x", count: 38)
        let url = URL(string: "me.sodai.app://auth/callback?state=" + attempt.state + "&code=" + code)!
        #expect(try attempt.code(from: url) == code)
        // The server clears inherited OAuth fragments with an explicit empty fragment.
        #expect(try attempt.code(from: URL(string: url.absoluteString + "#")!) == code)
        #expect(throws: AuthFailure.invalidCallback(.credentials)) {
            try attempt.code(
                from: URL(
                    string: "me.sodai.app://user@auth/callback?state=" + attempt.state + "&code=" + code)!)
        }
        #expect(throws: AuthFailure.invalidCallback(.fragment)) {
            try attempt.code(from: URL(string: url.absoluteString + "#unexpected")!)
        }
    }

    @Test func sessionSurvivesNewStoreAndNetworkFailureButNotRevocation() async throws {
        let storage = MemoryCredentials()
        let api = FakeAuthClient()
        let first = AuthStore(client: api, storage: storage)
        await first.signIn(authenticate: successfulCallback)
        #expect(first.user == api.credential.user)
        #expect(storage.saved == api.credential)
        let second = AuthStore(client: api, storage: storage)
        await second.restore()
        #expect(second.status == .signedIn(api.credential.user))
        api.restoreError = URLError(.notConnectedToInternet)
        await second.restore()
        #expect(second.status == .offline(api.credential.user))
        #expect(storage.saved != nil)
        api.restoreError = AuthFailure.unauthenticated
        await second.restore()
        #expect(second.status == .signedOut)
        #expect(storage.saved == nil)
    }

    @Test func badCallbackNeverExchangesOrReplacesExistingSession() async throws {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        await auth.signIn { _ in URL(string: "me.sodai.app://auth/callback?state=wrong&code=wrong")! }
        #expect(api.exchanges == 0)
        #expect(auth.user == api.credential.user)
        #expect(storage.saved == api.credential)
    }

    @Test func logoutFailureCanBeRetriedAndSuccessfulLogoutRemovesCredential() async {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        api.logoutError = URLError(.notConnectedToInternet)
        await auth.signOut()
        #expect(storage.saved != nil)
        api.logoutError = nil
        await auth.signOut()
        #expect(storage.saved == nil)
        #expect(auth.status == .signedOut)
    }

    @Test func keychainRoundTripAndOriginIsolation() throws {
        let origin = URL(string: "https://" + UUID().uuidString.lowercased() + ".example.test")!
        let store = KeychainCredentialStore(origin: origin)
        defer { try? store.clear() }
        let value = FakeAuthClient().credential
        try store.save(value)
        #expect(try KeychainCredentialStore(origin: origin).load() == value)
        #expect(
            try KeychainCredentialStore(origin: URL(string: "https://different.example.test")!).load() == nil)
        try store.clear()
        #expect(try store.load() == nil)
    }

    @Test(.timeLimit(.minutes(1))) func staleTokenRejectionCannotClearNewLogin() async throws {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        let response = AuthResponseGate<String>()
        api.tokenHandler = { _ in try await response.wait() }
        let pending = Task { try await auth.accessToken() }
        await response.waitUntilStarted()
        api.credential = .init(
            token: "new-session", expiresAt: "2099-01-01T00:00:00Z",
            user: .init(id: "user-2", name: "New account", email: "new@example.test"))
        await auth.signIn(authenticate: successfulCallback)
        response.finish(.failure(AuthFailure.unauthenticated))
        await #expect(throws: CancellationError.self) { try await pending.value }
        #expect(auth.status == .signedIn(api.credential.user))
        #expect(storage.saved == api.credential)
    }

    @Test(.timeLimit(.minutes(1))) func tokenReceivedAfterLogoutCannotBeUsed() async throws {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        let response = AuthResponseGate<String>()
        api.tokenHandler = { _ in try await response.wait() }
        let pending = Task { try await auth.accessToken() }
        await response.waitUntilStarted()
        await auth.signOut()
        response.finish(.success("old.jwt.token"))
        await #expect(throws: CancellationError.self) { try await pending.value }
        #expect(auth.status == .signedOut)
        #expect(storage.saved == nil)
    }

    @Test(.timeLimit(.minutes(1))) func delayedLogoutCannotRemoveNewLogin() async {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        let response = AuthResponseGate<Void>()
        api.logoutHandler = { _ in try await response.wait() }
        let pending = Task { await auth.signOut() }
        await response.waitUntilStarted()
        api.credential = .init(
            token: "new-session", expiresAt: "2099-01-01T00:00:00Z",
            user: .init(id: "user-2", name: "New account", email: "new@example.test"))
        await auth.signIn(authenticate: successfulCallback)
        response.finish(.success(()))
        await pending.value
        #expect(auth.status == .signedIn(api.credential.user))
        #expect(storage.saved == api.credential)
    }

    @Test(.timeLimit(.minutes(1))) func loginCompletedAfterLogoutIsRevoked() async {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        let auth = AuthStore(client: api, storage: storage)
        let response = AuthResponseGate<SessionCredential>()
        api.exchangeHandler = { try await response.wait() }
        let pending = Task { await auth.signIn(authenticate: successfulCallback) }
        await response.waitUntilStarted()
        await auth.signOut()
        response.finish(.success(api.credential))
        await pending.value
        #expect(auth.status == .signedOut)
        #expect(storage.saved == nil)
        #expect(api.revokedTokens == [api.credential.token])
    }

    @Test(.timeLimit(.minutes(1))) func olderRestoreCannotInvalidateNewerRestore() async {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        let response = AuthResponseGate<SessionCredential>()
        api.restoreHandler = { _ in try await response.wait() }
        let pending = Task { await auth.restore() }
        await response.waitUntilStarted()
        api.restoreHandler = nil
        await auth.restore()
        response.finish(.failure(AuthFailure.unauthenticated))
        await pending.value
        #expect(auth.status == .signedIn(api.credential.user))
        #expect(storage.saved == api.credential)
    }

    @Test(.timeLimit(.minutes(1))) func restoreStartedDuringLogoutCannotResurrectSession() async {
        let api = FakeAuthClient()
        let storage = MemoryCredentials()
        storage.saved = api.credential
        let auth = AuthStore(client: api, storage: storage)
        await auth.restore()
        let logoutResponse = AuthResponseGate<Void>()
        api.logoutHandler = { _ in try await logoutResponse.wait() }
        let logout = Task { await auth.signOut() }
        await logoutResponse.waitUntilStarted()
        let restoreResponse = AuthResponseGate<SessionCredential>()
        api.restoreHandler = { _ in try await restoreResponse.wait() }
        let restore = Task { await auth.restore() }
        await restoreResponse.waitUntilStarted()
        logoutResponse.finish(.success(()))
        await logout.value
        restoreResponse.finish(.success(api.credential))
        await restore.value
        #expect(auth.status == .signedOut)
        #expect(storage.saved == nil)
    }

    @Test func productionConfigurationRejectsUntrustedURLForms() {
        #expect(!AppConfiguration.isValid(URL(string: "http://app.sodai.me")!))
        #expect(!AppConfiguration.isValid(URL(string: "https://user:password@app.sodai.me")!))
        #expect(!AppConfiguration.isValid(URL(string: "https://app.sodai.me/path")!))
        #expect(AppConfiguration.isValid(URL(string: "http://localhost:13209")!, allowLocalHTTP: true))
        #expect(!AppConfiguration.isValid(URL(string: "http://public.example")!, allowLocalHTTP: true))
    }
}

@MainActor
private final class MemoryCredentials: CredentialStoring {
    var saved: SessionCredential?
    func load() throws -> SessionCredential? { saved }
    func save(_ credential: SessionCredential) throws { saved = credential }
    func clear() throws { saved = nil }
}

@MainActor
private final class FakeAuthClient: AuthServing {
    let origin = URL(string: "https://auth.example.test")!
    var credential = SessionCredential(
        token: "test-session", expiresAt: "2099-01-01T00:00:00Z",
        user: AuthUser(id: "user-1", name: "Tester", email: "test@example.test"))
    var restoreError: Error?
    var logoutError: Error?
    var exchanges = 0
    var revokedTokens: [String] = []
    var restoreHandler: ((String) async throws -> SessionCredential)?
    var tokenHandler: ((String) async throws -> String)?
    var exchangeHandler: (() async throws -> SessionCredential)?
    var logoutHandler: ((String) async throws -> Void)?
    func capabilities() async throws -> AuthCapabilities { .init(google: true, mobile: true) }
    func exchange(code: String, attempt: OAuthAttempt) async throws -> SessionCredential {
        exchanges += 1
        if let exchangeHandler { return try await exchangeHandler() }
        return credential
    }
    func restore(token: String) async throws -> SessionCredential {
        if let restoreHandler { return try await restoreHandler(token) }
        if let restoreError { throw restoreError }
        return credential
    }
    func accessToken(sessionToken: String) async throws -> String {
        if let tokenHandler { return try await tokenHandler(sessionToken) }
        return "test.jwt.token"
    }
    func signOut(token: String) async throws {
        revokedTokens.append(token)
        if let logoutHandler {
            try await logoutHandler(token)
            return
        }
        if let logoutError { throw logoutError }
    }
}

@MainActor
private final class AuthResponseGate<Value: Sendable> {
    private var continuation: CheckedContinuation<Value, Error>?

    func wait() async throws -> Value {
        try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        while continuation == nil { await Task.yield() }
    }

    func finish(_ result: Result<Value, Error>) {
        continuation?.resume(with: result)
        continuation = nil
    }
}

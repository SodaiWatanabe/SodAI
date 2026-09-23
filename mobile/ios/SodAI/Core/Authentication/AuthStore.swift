import AuthenticationServices
import Foundation
import Observation

@MainActor @Observable
final class AuthStore {
    enum Status: Equatable {
        case signedOut, restoring
        case signedIn(AuthUser)
        case offline(AuthUser)
    }

    private(set) var status = Status.restoring
    private(set) var isSigningIn = false
    private(set) var errorMessage: String?
    private(set) var googleAvailable = false
    private let client: any AuthServing
    private let storage: any CredentialStoring
    private var credential: SessionCredential?
    private var generation = 0
    private var restoreVersion = 0

    init(client: any AuthServing, storage: any CredentialStoring) {
        self.client = client
        self.storage = storage
    }

    var user: AuthUser? {
        switch status {
        case .signedIn(let user), .offline(let user): user
        default: nil
        }
    }

    func prepare() async {
        await restore()
        do {
            let result = try await client.capabilities()
            googleAvailable = result.google && result.mobile == true
        } catch { googleAvailable = false }
    }

    func restore() async {
        let currentGeneration = generation
        restoreVersion += 1
        let request = restoreVersion
        do {
            guard let saved = try storage.load() else {
                credential = nil
                status = .signedOut
                return
            }
            credential = saved
            let renewed = try await client.restore(token: saved.token)
            guard generation == currentGeneration, request == restoreVersion else { return }
            try storage.save(renewed)
            credential = renewed
            status = .signedIn(renewed.user)
            errorMessage = nil
        } catch AuthFailure.unauthenticated {
            guard generation == currentGeneration, request == restoreVersion else { return }
            do {
                try storage.clear()
                credential = nil
                status = .signedOut
                errorMessage = AuthFailure.unauthenticated.localizedDescription
            } catch { errorMessage = error.localizedDescription }
        } catch {
            guard generation == currentGeneration, request == restoreVersion else { return }
            // A network failure must not silently destroy a valid stored session.
            status = credential.map { .offline($0.user) } ?? .signedOut
            errorMessage = error.localizedDescription
        }
    }

    func signIn(authenticate: (URL) async throws -> URL) async {
        guard !isSigningIn else { return }
        isSigningIn = true
        errorMessage = nil
        defer { isSigningIn = false }
        generation += 1
        let currentGeneration = generation
        do {
            let attempt = try OAuthAttempt()
            let callback = try await authenticate(attempt.authorizationURL(origin: client.origin))
            guard generation == currentGeneration else { return }
            let code = try attempt.code(from: callback)
            let result = try await client.exchange(code: code, attempt: attempt)
            guard generation == currentGeneration else {
                try? await client.signOut(token: result.token)
                return
            }
            do { try storage.save(result) } catch {
                try? await client.signOut(token: result.token)
                throw error
            }
            generation += 1
            credential = result
            status = .signedIn(result.user)
        } catch let error as ASWebAuthenticationSessionError where error.code == .canceledLogin {
            // Closing the system sheet leaves any existing account untouched.
        } catch { if generation == currentGeneration { errorMessage = error.localizedDescription } }
    }

    func signOut() async {
        generation += 1
        let currentGeneration = generation
        do {
            // Keep the credential if revocation fails, so logout can be retried.
            if let credential { try await client.signOut(token: credential.token) }
            guard generation == currentGeneration else { return }
            try storage.clear()
            generation += 1
            credential = nil
            status = .signedOut
            errorMessage = nil
        } catch {
            if generation == currentGeneration {
                errorMessage = "ログアウトを完了できませんでした。通信を確認して再試行してください。"
            }
        }
    }

    func accessToken() async throws -> String {
        guard let credential else { throw AuthFailure.unauthenticated }
        let currentGeneration = generation
        do {
            let token = try await client.accessToken(sessionToken: credential.token)
            guard generation == currentGeneration, self.credential?.token == credential.token else {
                throw CancellationError()
            }
            return token
        } catch AuthFailure.unauthenticated {
            guard generation == currentGeneration, self.credential?.token == credential.token else {
                throw CancellationError()
            }
            try storage.clear()
            generation += 1
            self.credential = nil
            status = .signedOut
            throw AuthFailure.unauthenticated
        }
    }
}

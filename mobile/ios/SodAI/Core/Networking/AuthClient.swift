import Foundation

struct AuthCapabilities: Decodable, Sendable {
    let google: Bool
    let mobile: Bool?
}

@MainActor
protocol AuthServing {
    var origin: URL { get }
    func capabilities() async throws -> AuthCapabilities
    func exchange(code: String, attempt: OAuthAttempt) async throws -> SessionCredential
    func restore(token: String) async throws -> SessionCredential
    func accessToken(sessionToken: String) async throws -> String
    func signOut(token: String) async throws
}

private final class NoRedirectDelegate: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(
        _ session: URLSession, task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
        completionHandler: @escaping @Sendable (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}

@MainActor
final class AuthClient: AuthServing {
    let origin: URL
    private let session: URLSession
    private let decoder = JSONDecoder()

    init(origin: URL, session: URLSession? = nil) {
        self.origin = origin
        let config = URLSessionConfiguration.ephemeral
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.urlCache = nil
        self.session =
            session ?? URLSession(configuration: config, delegate: NoRedirectDelegate(), delegateQueue: nil)
    }

    func capabilities() async throws -> AuthCapabilities {
        try decoder.decode(AuthCapabilities.self, from: await request("capabilities"))
    }

    func exchange(code: String, attempt: OAuthAttempt) async throws -> SessionCredential {
        let data = try await request(
            "mobile/exchange",
            body: [
                "code": code, "state": attempt.state, "code_verifier": attempt.verifier,
            ])
        return try decoder.decode(SessionCredential.self, from: data)
    }

    func restore(token: String) async throws -> SessionCredential {
        // POST renews the session: the service deliberately defers refresh on GET.
        let data = try await request("get-session", token: token, body: [:])
        if String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) == "null" {
            throw AuthFailure.unauthenticated
        }
        struct Payload: Decodable {
            struct Session: Decodable {
                let token: String
                let expiresAt: String
            }
            let session: Session
            let user: AuthUser
        }
        let payload = try decoder.decode(Payload.self, from: data)
        return SessionCredential(
            token: payload.session.token, expiresAt: payload.session.expiresAt, user: payload.user)
    }

    func accessToken(sessionToken: String) async throws -> String {
        struct Payload: Decodable { let token: String }
        let data = try await request("token", token: sessionToken)
        return try decoder.decode(Payload.self, from: data).token
    }

    func signOut(token: String) async throws {
        _ = try await request("sign-out", token: token, body: [:])
    }

    private func request(_ path: String, token: String? = nil, body: [String: String]? = nil) async throws
        -> Data
    {
        var request = URLRequest(url: origin.appending(path: "api/auth/" + path))
        request.timeoutInterval = 20
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization") }
        if let body {
            request.httpMethod = "POST"
            request.httpBody = try JSONEncoder().encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(
                origin.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")),
                forHTTPHeaderField: "Origin")
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw AuthFailure.invalidResponse }
        if http.statusCode == 401 { throw AuthFailure.unauthenticated }
        guard (200..<300).contains(http.statusCode) else { throw AuthFailure.unavailable }
        return data
    }
}

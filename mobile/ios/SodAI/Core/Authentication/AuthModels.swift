import CryptoKit
import Foundation
import Security

struct AuthUser: Codable, Equatable, Sendable {
    let id: String
    let name: String
    let email: String
}

struct SessionCredential: Codable, Equatable, Sendable {
    let token: String
    let expiresAt: String
    let user: AuthUser
}

enum AuthFailure: LocalizedError, Equatable {
    case invalidCallback(CallbackIssue)
    case expiredAttempt, unauthenticated, unavailable, invalidResponse, secureStorage
    case keychainStatus(Int32)

    var errorDescription: String? {
        switch self {
        case .invalidCallback(let issue):
            #if DEBUG
                "ログインを確認できませんでした。もう一度お試しください。（診断: \(issue.rawValue)）"
            #else
                "ログインを確認できませんでした。もう一度お試しください。"
            #endif
        case .expiredAttempt: "ログインの有効時間が過ぎました。もう一度お試しください。"
        case .unauthenticated: "もう一度ログインしてください。"
        case .unavailable: "現在ログインを利用できません。しばらくしてからお試しください。"
        case .invalidResponse: "サーバーの応答を確認できませんでした。"
        case .secureStorage, .keychainStatus: "ログイン情報を安全に保存できませんでした。"
        }
    }
}

/// Only fixed reason identifiers are exposed; callback URLs and credentials are never logged.
enum CallbackIssue: String, Equatable {
    case malformedURL = "CB01"
    case scheme = "CB02"
    case host = "CB03"
    case path = "CB04"
    case credentials = "CB05"
    case port = "CB06"
    case fragment = "CB07"
    case stateCount = "CB08"
    case stateMismatch = "CB09"
    case duplicateResult = "CB10"
    case missingCode = "CB11"
    case malformedCode = "CB12"
}

struct OAuthAttempt: Sendable {
    static let callbackScheme = "me.sodai.app"
    let state: String
    let verifier: String
    let createdAt: Date

    init(now: Date = .now) throws {
        state = try Self.random()
        verifier = try Self.random()
        createdAt = now
    }

    var challenge: String {
        Data(SHA256.hash(data: Data(verifier.utf8))).base64URL
    }

    func authorizationURL(origin: URL) throws -> URL {
        var parts = URLComponents(
            url: origin.appending(path: "api/auth/mobile/start"),
            resolvingAgainstBaseURL: false)!
        parts.queryItems = [
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "code_challenge", value: challenge),
        ]
        guard let url = parts.url else { throw AuthFailure.invalidResponse }
        return url
    }

    func code(from callback: URL, now: Date = .now) throws -> String {
        guard now.timeIntervalSince(createdAt) >= 0,
            now.timeIntervalSince(createdAt) < 600
        else { throw AuthFailure.expiredAttempt }
        guard let parts = URLComponents(url: callback, resolvingAgainstBaseURL: false)
        else { throw AuthFailure.invalidCallback(.malformedURL) }
        guard parts.scheme == Self.callbackScheme else { throw AuthFailure.invalidCallback(.scheme) }
        guard parts.host == "auth" else { throw AuthFailure.invalidCallback(.host) }
        guard parts.path == "/callback" else { throw AuthFailure.invalidCallback(.path) }
        guard parts.user == nil, parts.password == nil else {
            throw AuthFailure.invalidCallback(.credentials)
        }
        guard parts.port == nil else { throw AuthFailure.invalidCallback(.port) }
        // The server uses an empty fragment to stop OAuth redirect inheritance.
        guard parts.fragment == nil || parts.fragment == "" else {
            throw AuthFailure.invalidCallback(.fragment)
        }
        let items = parts.queryItems ?? []
        guard items.filter({ $0.name == "state" }).count == 1 else {
            throw AuthFailure.invalidCallback(.stateCount)
        }
        guard items.first(where: { $0.name == "state" })?.value == state else {
            throw AuthFailure.invalidCallback(.stateMismatch)
        }
        guard items.filter({ $0.name == "code" }).count <= 1,
            items.filter({ $0.name == "error" }).count <= 1
        else { throw AuthFailure.invalidCallback(.duplicateResult) }
        if items.contains(where: { $0.name == "error" }) { throw AuthFailure.unauthenticated }
        guard let code = items.first(where: { $0.name == "code" })?.value
        else { throw AuthFailure.invalidCallback(.missingCode) }
        guard code.range(of: "^[A-Za-z0-9_-]{43}$", options: .regularExpression) != nil
        else { throw AuthFailure.invalidCallback(.malformedCode) }
        return code
    }

    private static func random() throws -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess
        else { throw AuthFailure.secureStorage }
        return Data(bytes).base64URL
    }
}

extension Data {
    fileprivate var base64URL: String {
        base64EncodedString().replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
}

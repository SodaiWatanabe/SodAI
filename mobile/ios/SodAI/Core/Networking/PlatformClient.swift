import Foundation
import Security

struct PlatformError: Error, LocalizedError, Sendable {
    let status: Int
    var errorDescription: String? {
        switch status {
        case 401: "ログインし直してください。"
        case 402: "クレジットが不足しています。アカウントメニューで無料クレジットの残量を確認できます。"
        case 403: "この操作を利用できません。"
        case 404: "対象が見つかりませんでした。"
        case 409: "状態が更新されています。最新の状態を確認してください。"
        case 422: "入力内容や選択条件を確認してください。"
        case 429: "現在、回答の生成が混み合っています。少し待ってからもう一度お試しください。"
        case 503: "回答モデルを一時的に利用できません。少し待ってからもう一度お試しください。"
        default: "SodAI APIへ接続できませんでした。もう一度お試しください。"
        }
    }
}
@MainActor protocol PlatformServing {
    func request(_ path: String, method: String, body: Data?, headers: [String: String]) async throws -> Data
}
extension PlatformServing {
    func get<T: Decodable & Sendable>(_ path: String) async throws -> T {
        try await call(path)
    }
    func call<T: Decodable & Sendable>(
        _ path: String, method: String = "GET", body: Data? = nil,
        headers: [String: String] = [:]
    ) async throws -> T {
        try JSONDecoder().decode(
            T.self, from: await request(path, method: method, body: body, headers: headers))
    }
    func perform(_ path: String, method: String, body: Data? = nil, headers: [String: String] = [:])
        async throws
    {
        _ = try await request(path, method: method, body: body, headers: headers)
    }
}
func jsonBody(_ values: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: values) }

/// Isolated from browser authentication cookies. Only the API guest credential is persisted.
@MainActor final class GuestCredentialStore {
    private let query: [String: Any]
    init(origin: URL) {
        query = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "me.sodai.app.guest." + origin.absoluteString,
            kSecAttrAccount as String: "guest", kSecAttrSynchronizable as String: false,
        ]
    }
    func load() throws -> String? {
        var lookup = query
        lookup[kSecReturnData as String] = true
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data,
            let token = String(data: data, encoding: .utf8)
        else { throw AuthFailure.secureStorage }
        return token
    }
    func save(_ token: String) throws {
        let values: [String: Any] = [
            kSecValueData as String: Data(token.utf8),
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        let status = SecItemUpdate(query as CFDictionary, values as CFDictionary)
        if status == errSecItemNotFound {
            guard SecItemAdd(query.merging(values) { _, new in new } as CFDictionary, nil) == errSecSuccess
            else { throw AuthFailure.secureStorage }
        } else if status != errSecSuccess {
            throw AuthFailure.secureStorage
        }
    }
}
final class PlatformRedirectDelegate: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(
        _ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest, completionHandler: @escaping @Sendable (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}
@MainActor final class PlatformClient: PlatformServing {
    let origin: URL
    private let session: URLSession
    private let auth: AuthStore
    private let guestStorage: GuestCredentialStore
    private var guestToken: String?
    private var bootstrap: Task<Void, Error>?
    init(origin: URL, auth: AuthStore, session: URLSession? = nil) {
        self.origin = origin
        self.auth = auth
        guestStorage = GuestCredentialStore(origin: origin)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.urlCache = nil
        self.session =
            session
            ?? URLSession(
                configuration: configuration, delegate: PlatformRedirectDelegate(), delegateQueue: nil)
    }
    private func ensureGuest() async throws {
        if guestToken != nil { return }
        if let saved = try guestStorage.load() {
            guestToken = saved
            return
        }
        if let bootstrap { return try await bootstrap.value }
        // Serialize creation: parallel first requests must not create different guest spaces.
        let task = Task { @MainActor in
            _ = try await self.send("/answerers", method: "GET", body: nil, headers: [:], token: nil)
        }
        bootstrap = task
        defer { bootstrap = nil }
        try await task.value
    }
    func request(_ path: String, method: String, body: Data?, headers: [String: String]) async throws -> Data
    {
        let identity = auth.user?.id
        if identity == nil { try await ensureGuest() }
        let token = identity == nil ? nil : try await auth.accessToken()
        guard auth.user?.id == identity else { throw CancellationError() }
        let data = try await send(path, method: method, body: body, headers: headers, token: token)
        guard auth.user?.id == identity else { throw CancellationError() }
        return data
    }
    private func send(_ path: String, method: String, body: Data?, headers: [String: String], token: String?)
        async throws -> Data
    {
        guard path.hasPrefix("/"), !path.contains(".."),
            let url = URL(string: origin.appendingPathComponent("api/v1").absoluteString + path),
            url.host == origin.host
        else { throw URLError(.badURL) }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30)
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(origin.absoluteString, forHTTPHeaderField: "Origin")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let token {
            request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        } else if let guestToken {
            request.setValue("sodai_guest=" + guestToken, forHTTPHeaderField: "Cookie")
        }
        for (key, value) in headers { request.setValue(value, forHTTPHeaderField: key) }
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        if token == nil {
            let fields = response.allHeaderFields.reduce(into: [String: String]()) { result, item in
                if let key = item.key as? String, let value = item.value as? String { result[key] = value }
            }
            if let cookie = HTTPCookie.cookies(withResponseHeaderFields: fields, for: url).first(where: {
                $0.name == "sodai_guest"
            }) {
                try guestStorage.save(cookie.value)
                guestToken = cookie.value
            }
        }
        guard (200..<300).contains(response.statusCode) else {
            throw PlatformError(status: response.statusCode)
        }
        return data
    }
}

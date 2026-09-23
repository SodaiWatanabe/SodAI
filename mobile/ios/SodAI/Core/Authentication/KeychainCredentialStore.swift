import Foundation
import Security

@MainActor
protocol CredentialStoring {
    func load() throws -> SessionCredential?
    func save(_ credential: SessionCredential) throws
    func clear() throws
}

@MainActor
final class KeychainCredentialStore: CredentialStoring {
    private let service: String

    init(origin: URL) {
        // Credentials from a test server must never be sent to production.
        service = "me.sodai.app.session." + origin.absoluteString
    }

    private var query: [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "session",
            kSecAttrSynchronizable as String: false,
        ]
    }

    func load() throws -> SessionCredential? {
        var lookup = query
        lookup[kSecReturnData as String] = true
        lookup[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw AuthFailure.keychainStatus(status) }
        guard let data = result as? Data else { throw AuthFailure.secureStorage }
        do { return try JSONDecoder().decode(SessionCredential.self, from: data) } catch {
            throw AuthFailure.secureStorage
        }
    }

    func save(_ credential: SessionCredential) throws {
        let data = try JSONEncoder().encode(credential)
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            let item = query.merging(attributes) { _, new in new }
            let addStatus = SecItemAdd(item as CFDictionary, nil)
            guard addStatus == errSecSuccess else { throw AuthFailure.keychainStatus(addStatus) }
        } else if status != errSecSuccess {
            throw AuthFailure.keychainStatus(status)
        }
    }

    func clear() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw AuthFailure.keychainStatus(status)
        }
    }
}

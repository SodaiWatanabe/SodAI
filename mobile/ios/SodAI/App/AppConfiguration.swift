import Foundation

enum AppConfiguration {
    static var authOrigin: URL {
        #if DEBUG
            let args = ProcessInfo.processInfo.arguments
            if let index = args.firstIndex(of: "-auth-origin"), args.indices.contains(index + 1),
                let url = URL(string: args[index + 1]), isValid(url, allowLocalHTTP: true)
            {
                var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
                components.path = ""
                return components.url!
            }
        #endif
        return URL(string: "https://app.sodai.me")!
    }

    static func isValid(_ url: URL, allowLocalHTTP: Bool = false) -> Bool {
        guard url.host != nil, url.user == nil, url.password == nil,
            url.path.isEmpty || url.path == "/", url.query == nil, url.fragment == nil
        else { return false }
        if url.scheme == "https" { return true }
        return allowLocalHTTP && url.scheme == "http" && ["localhost", "127.0.0.1"].contains(url.host)
    }
}

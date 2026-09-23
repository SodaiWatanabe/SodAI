import SwiftUI

@main
struct SodAIApp: App {
    @State private var auth: AuthStore
    @State private var platform: PlatformStore
    @Environment(\.scenePhase) private var scenePhase
    init() {
        #if DEBUG
            let arguments = ProcessInfo.processInfo.arguments
            if let index = arguments.firstIndex(of: "-platform-ui-fixture") {
                let fixture = UITestFixture(
                    scenario: index + 1 < arguments.count ? arguments[index + 1] : "assigned")
                let auth = AuthStore(client: fixture, storage: fixture)
                _auth = State(initialValue: auth)
                _platform = State(
                    initialValue: PlatformStore(api: fixture, origin: fixture.origin, realtimeEnabled: false))
                return
            }
        #endif
        let origin = AppConfiguration.authOrigin
        let storage = KeychainCredentialStore(origin: origin)
        #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("-reset-test-session") { try? storage.clear() }
        #endif
        let auth = AuthStore(client: AuthClient(origin: origin), storage: storage)
        _auth = State(initialValue: auth)
        let api = PlatformClient(origin: origin, auth: auth)
        _platform = State(initialValue: PlatformStore(api: api, origin: origin))
    }
    var body: some Scene {
        WindowGroup {
            HomeView()
                .tint(SodAIStyle.ink)
                .preferredColorScheme(fixtureColorScheme)
                .environment(auth).environment(platform).environment(platform.chat).environment(
                    platform.brain
                )
                .task { await auth.prepare() }
                .task(id: auth.status == .restoring ? "restoring" : (auth.user?.id ?? "guest")) {
                    if auth.status != .restoring { await platform.activate(identity: auth.user?.id) }
                }
                .onChange(of: scenePhase) { _, phase in
                    if phase == .background {
                        platform.suspend()
                    } else if phase == .active {
                        Task {
                            if auth.user != nil { await auth.restore() }
                            await platform.resume()
                        }
                    }
                }
        }
    }
    private var fixtureColorScheme: ColorScheme? {
        #if DEBUG
            let arguments = ProcessInfo.processInfo.arguments
            if arguments.contains("-platform-ui-fixture"), arguments.contains("-ui-dark") { return .dark }
            if arguments.contains("-platform-ui-fixture"), arguments.contains("-ui-light") { return .light }
        #endif
        return nil
    }
}

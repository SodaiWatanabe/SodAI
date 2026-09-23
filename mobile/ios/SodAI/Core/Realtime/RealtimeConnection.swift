import Foundation
import Observation

@MainActor @Observable
final class RealtimeConnection {
    private(set) var connected = false
    private var task: Task<Void, Never>?
    private var socket: URLSessionWebSocketTask?
    private var watchdog: Task<Void, Never>?
    private var lastMessage = Date()
    private var cursor: Int?
    private var generation = 0
    private let api: any PlatformServing
    private let origin: URL
    private let session: URLSession
    init(api: any PlatformServing, origin: URL) {
        self.api = api
        self.origin = origin
        let config = URLSessionConfiguration.ephemeral
        config.httpCookieStorage = nil
        config.urlCache = nil
        session = URLSession(configuration: config, delegate: PlatformRedirectDelegate(), delegateQueue: nil)
    }
    func stop(resetCursor: Bool = false) {
        generation += 1
        task?.cancel()
        watchdog?.cancel()
        socket?.cancel(with: .goingAway, reason: nil)
        task = nil
        socket = nil
        watchdog = nil
        connected = false
        if resetCursor { cursor = nil }
    }
    func start(onEvent: @escaping @MainActor (RealtimeEvent) -> Void) {
        guard task == nil else { return }
        let version = generation
        task = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled, version == self.generation {
                do {
                    let ticket: RealtimeTicket = try await self.api.call("/realtime/tickets", method: "POST")
                    try Task.checkCancellation()
                    guard version == self.generation else { return }
                    // The server's in-memory sequence restarts when the backend restarts.
                    if let cursor = self.cursor, cursor > ticket.cursor { self.cursor = ticket.cursor }
                    var url = URLComponents(url: self.origin, resolvingAgainstBaseURL: false)!
                    url.scheme = url.scheme == "https" ? "wss" : "ws"
                    url.path = "/api/v1/realtime"
                    url.queryItems = [
                        .init(name: "ticket", value: ticket.ticket),
                        .init(name: "after", value: String(self.cursor ?? ticket.cursor)),
                    ]
                    let socket = self.session.webSocketTask(with: url.url!)
                    self.socket = socket
                    self.lastMessage = Date()
                    socket.resume()
                    self.watchdog = Task { [weak self, weak socket] in
                        while !Task.isCancelled {
                            do { try await Task.sleep(for: .seconds(15)) } catch { return }
                            guard let self, version == self.generation else { return }
                            if Date().timeIntervalSince(self.lastMessage) > 45 {
                                socket?.cancel(with: .goingAway, reason: nil)
                                return
                            }
                        }
                    }
                    while !Task.isCancelled, version == self.generation {
                        let message = try await socket.receive()
                        try Task.checkCancellation()
                        let data: Data
                        switch message {
                        case .data(let value): data = value
                        case .string(let value): data = Data(value.utf8)
                        @unknown default: continue
                        }
                        let event = try JSONDecoder().decode(RealtimeEvent.self, from: data)
                        self.lastMessage = Date()
                        if event.type != "sync.required", let sequence = event.sequence,
                            let cursor = self.cursor, sequence <= cursor
                        {
                            continue
                        }
                        if let next = event.sequence ?? event.cursor {
                            self.cursor = max(self.cursor ?? 0, next)
                        }
                        if event.type == "ready" { self.connected = true }
                        if event.type != "ping" { onEvent(event) }
                    }
                } catch {
                    guard version == self.generation, !Task.isCancelled else { return }
                    self.connected = false
                }
                self.watchdog?.cancel()
                self.socket?.cancel(with: .goingAway, reason: nil)
                do { try await Task.sleep(for: .milliseconds(1200)) } catch { return }
            }
        }
    }
}

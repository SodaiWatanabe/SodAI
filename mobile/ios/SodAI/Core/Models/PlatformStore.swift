import Foundation
import Observation
import UIKit

@MainActor @Observable
final class PlatformStore {
    let chat: ConversationStore
    let brain: BrainStore
    let realtime: RealtimeConnection
    let realtimeEnabled: Bool
    private(set) var credits: CreditBalance?
    private(set) var initialized = false
    private(set) var active = true
    private let api: any PlatformServing
    private let origin: URL
    private var identity: String?
    private var generation = 0
    private var timer: Task<Void, Never>?
    private var reconcileTask: Task<Void, Never>?
    private var needsReconcile = false
    private var reconcileVersion = 0
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid

    init(api: any PlatformServing, origin: URL, realtimeEnabled: Bool = true) {
        self.realtimeEnabled = realtimeEnabled
        self.api = api
        self.origin = origin
        chat = ConversationStore(api: api)
        brain = BrainStore(api: api)
        realtime = RealtimeConnection(api: api, origin: origin)
    }
    func activate(identity: String?) async {
        generation += 1
        let version = generation
        self.identity = identity
        initialized = false
        realtime.stop(resetCursor: true)
        timer?.cancel()
        timer = nil
        reconcileTask?.cancel()
        reconcileTask = nil
        reconcileVersion += 1
        needsReconcile = false
        chat.reset(identity: identity ?? "guest", origin: origin)
        brain.reset(authenticated: identity != nil)
        credits = nil
        await chat.load()
        guard version == generation, !Task.isCancelled else { return }
        if identity != nil { await refreshCredits() }
        guard version == generation, !Task.isCancelled else { return }
        initialized = true
        if active { start() }
    }
    func refreshCredits() async {
        guard identity != nil else { return }
        let version = generation
        do {
            let balance: CreditBalance = try await api.get("/credits")
            if version == generation { credits = balance }
        } catch {
            // Keep the last known balance until the next refresh.
        }
    }
    func setBrainVisible(_ visible: Bool) async {
        brain.visible = visible
        if visible, initialized, identity != nil {
            await brain.refresh()
            await brain.refreshHistory()
        }
    }
    private func start() {
        if realtimeEnabled {
            realtime.start { [weak self] event in
                guard let self else { return }
                let chatSync = self.chat.receive(event)
                let brainSync = self.brain.receive(event)
                if event.type == "ready" || event.type == "sync.required" || chatSync || brainSync
                    || event.type.hasPrefix("thread.")
                    || ["entry.created", "response.completed", "response.failed", "response.cancelled"]
                        .contains(event.type)
                {
                    self.scheduleReconcile()
                }
            }
        }
        guard timer == nil else { return }
        let version = generation
        timer = Task { [weak self] in
            var ticks = 0
            while !Task.isCancelled {
                do { try await Task.sleep(for: .milliseconds(250)) } catch { return }
                guard let self, self.active, version == self.generation else { return }
                ticks += 1
                await self.brain.tick()
                if ticks % 40 == 0 {
                    await self.brain.heartbeat()
                    if self.chat.responding || !self.realtime.connected { self.scheduleReconcile() }
                }
            }
        }
    }
    private func scheduleReconcile() {
        needsReconcile = true
        guard reconcileTask == nil else { return }
        let version = generation
        let request = reconcileVersion
        reconcileTask = Task { [weak self] in
            guard let self else { return }
            defer {
                if version == self.generation, request == self.reconcileVersion { self.reconcileTask = nil }
            }
            while self.needsReconcile, version == self.generation, !Task.isCancelled {
                self.needsReconcile = false
                await self.chat.refreshCurrent()
                await self.chat.refreshList()
                if self.identity != nil { await self.brain.refresh() }
                if self.brain.visible { await self.brain.refreshHistory() }
                await self.refreshCredits()
            }
        }
    }
    func suspend() {
        active = false
        realtime.stop()
        timer?.cancel()
        timer = nil
        reconcileTask?.cancel()
        reconcileTask = nil
        reconcileVersion += 1
        // iOS may suspend immediately. Use the finite background grace period to persist the draft.
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "Save Brain draft") {
            [weak self] in
            Task { @MainActor in self?.endBackgroundTask() }
        }
        Task { [weak self] in
            await self?.brain.flushDraft()
            self?.endBackgroundTask()
        }
    }
    private func endBackgroundTask() {
        if backgroundTask != .invalid {
            UIApplication.shared.endBackgroundTask(backgroundTask)
            backgroundTask = .invalid
        }
    }
    func resume() async {
        active = true
        guard initialized else { return }
        brain.requireValidation()
        if brain.visible { await brain.refresh() }
        start()
        scheduleReconcile()
    }
}

import XCTest

@MainActor
final class SodAIUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func launchFixture(_ scenario: String = "assigned", dark: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-platform-ui-fixture", scenario]
        app.launchArguments.append(dark ? "-ui-dark" : "-ui-light")
        app.launch()
        XCTAssertTrue(app.buttons["conversationMenu"].waitForExistence(timeout: 15))
        return app
    }
    func testChatSendSearchRenameArchive() {
        let app = launchFixture()
        attachScreenshot("Chat-Home")
        XCTAssertFalse(app.staticTexts["こんにちは。"].exists)
        XCTAssertFalse(app.scrollViews["conversationScroll"].exists)
        let field = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 10))
        field.tap()
        field.typeText("Native UI check")
        let send = app.buttons["sendMessage"]
        XCTAssertTrue(send.waitForExistence(timeout: 5))
        send.tap()
        let response = app.descendants(matching: .any).matching(identifier: "assistantMessage").firstMatch
        XCTAssertTrue(response.waitForExistence(timeout: 15), app.debugDescription)
        XCTAssertTrue(app.scrollViews["conversationScroll"].exists)
        attachScreenshot("Chat-Response")
        app.buttons["conversationMenu"].tap()
        attachScreenshot("Sidebar-Chat")
        let thread = app.buttons["Native UI check"].firstMatch
        XCTAssertTrue(thread.waitForExistence(timeout: 10), app.debugDescription)
        thread.press(forDuration: 1)
        app.buttons["名前を変更"].tap()
        let name = app.alerts.textFields.firstMatch
        name.tap()
        name.typeText(
            String(repeating: XCUIKeyboardKey.delete.rawValue, count: "Native UI check".count)
                + "Renamed conversation")
        app.alerts.buttons["保存"].tap()
        let renamed = app.buttons["threadRow:fixture-thread"].firstMatch
        XCTAssertTrue(renamed.waitForExistence(timeout: 10), app.debugDescription)
        app.buttons["toggleThreadSearch"].tap()
        let search = app.textFields["threadSearch"]
        search.tap()
        search.typeText("Renamed")
        XCTAssertTrue(renamed.waitForExistence(timeout: 10))
        attachScreenshot("Sidebar-Search")
        renamed.tap()
        XCTAssertTrue(response.waitForExistence(timeout: 10))
        app.buttons["conversationMenu"].tap()
        XCTAssertTrue(renamed.waitForExistence(timeout: 10))
        renamed.press(forDuration: 1)
        app.buttons["アーカイブ"].tap()
        XCTAssertTrue(app.staticTexts["会話はまだありません。"].waitForExistence(timeout: 10))
    }
    func testModelPickerSubmenusInBothAppearances() {
        for dark in [false, true] {
            let app = launchFixture("models", dark: dark)
            app.buttons["conversationMenu"].tap()
            app.buttons["newConversation"].tap()
            let input = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
            input.tap()
            input.typeText("Keep my model draft")
            let picker = app.buttons["modelPicker"]
            picker.tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertTrue(app.buttons["modelOption:asuka-1.1"].waitForExistence(timeout: 5))
            XCTAssertTrue(app.buttons["humanModels"].exists)
            XCTAssertTrue(app.buttons["pastModels"].exists)
            XCTAssertFalse(app.buttons["modelOption:human-lite"].exists)
            XCTAssertFalse(app.buttons["modelOption:hina"].exists)
            attachScreenshot(dark ? "Model-Picker-Root-Dark" : "Model-Picker-Root-Light")

            app.buttons["humanModels"].tap()
            XCTAssertTrue(app.buttons["modelOption:human-lite"].waitForExistence(timeout: 5))
            XCTAssertTrue(app.buttons["modelOption:human-standard"].exists)
            XCTAssertTrue(app.buttons["modelOption:human-pro"].exists)
            attachScreenshot(dark ? "Model-Picker-Human-Dark" : "Model-Picker-Human-Light")
            app.buttons["modelOption:human-standard"].tap()
            XCTAssertTrue(app.alerts.buttons["確認しました"].waitForExistence(timeout: 5))
            app.alerts.buttons["確認しました"].tap()
            XCTAssertEqual(picker.label, "モデル: Human Standard")
            XCTAssertFalse(app.buttons["humanModels"].exists)
            XCTAssertEqual(input.value as? String, "Keep my model draft")

            picker.tap()
            app.buttons["humanModels"].tap()
            XCTAssertTrue(app.buttons["modelOption:human-standard"].waitForExistence(timeout: 5))
            attachScreenshot(dark ? "Model-Picker-Human-Selected-Dark" : "Model-Picker-Human-Selected-Light")
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.7)).tap()
            XCTAssertTrue(app.buttons["modelOption:human-standard"].waitForNonExistence(timeout: 5))
            XCTAssertEqual(picker.label, "モデル: Human Standard")

            picker.tap()
            app.buttons["pastModels"].tap()
            XCTAssertTrue(app.buttons["modelOption:hina"].waitForExistence(timeout: 5))
            attachScreenshot(dark ? "Model-Picker-Legacy-Dark" : "Model-Picker-Legacy-Light")
            app.buttons["modelOption:hina"].tap()
            XCTAssertEqual(picker.label, "モデル: Hina")
            XCTAssertFalse(app.buttons["pastModels"].exists)
            picker.tap()
            app.buttons["modelOption:asuka-1.1"].tap()
            XCTAssertEqual(picker.label, "モデル: Asuka 1.1")
            XCTAssertEqual(input.value as? String, "Keep my model draft")
            app.terminate()
        }
    }
    func testHumanComposerShowsTwoRowsAndDepthOnlyWhileEditing() {
        for dark in [false, true] {
            let app = launchFixture("models", dark: dark)
            let model = app.buttons["modelPicker"]
            let composer = app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch
            let compactHeight = composer.frame.height
            model.tap()
            app.buttons["humanModels"].tap()
            app.buttons["modelOption:human-standard"].tap()
            XCTAssertTrue(app.alerts.buttons["確認しました"].waitForExistence(timeout: 5))
            app.alerts.buttons["確認しました"].tap()

            let input = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
            let depth = app.buttons["reasoningPicker"]
            let send = app.buttons["sendMessage"]
            XCTAssertFalse(depth.exists)
            let emptyHeight = composer.frame.height
            let singleTextLineHeight = input.frame.height
            XCTAssertEqual(emptyHeight, compactHeight, accuracy: 1)
            XCTAssertTrue(composer.frame.contains(send.frame))
            XCTAssertFalse(app.staticTexts["個人情報と機密情報は含めないでください。"].exists)
            XCTAssertFalse(
                app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "クレジット")).firstMatch.exists)
            attachScreenshot(dark ? "Human-Composer-Empty-Dark" : "Human-Composer-Empty-Light")

            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.02, dy: 0.3)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            XCTAssertTrue(depth.waitForExistence(timeout: 5))
            let editingHeight = composer.frame.height
            XCTAssertGreaterThan(editingHeight, emptyHeight)
            XCTAssertEqual(input.frame.height, singleTextLineHeight, accuracy: 1)
            XCTAssertTrue(composer.frame.contains(depth.frame))
            XCTAssertGreaterThanOrEqual(depth.frame.minY, input.frame.maxY)
            XCTAssertEqual(depth.frame.midY, send.frame.midY, accuracy: 1)
            XCTAssertLessThan(depth.frame.maxX, send.frame.minX)
            input.typeText("First line")
            XCTAssertEqual(composer.frame.height, editingHeight, accuracy: 1)
            attachScreenshot(dark ? "Human-Composer-Two-Rows-Dark" : "Human-Composer-Two-Rows-Light")
            depth.tap()
            XCTAssertTrue(app.buttons["reasoningOption:high"].waitForExistence(timeout: 5))
            attachScreenshot(dark ? "Human-Composer-Efforts-Dark" : "Human-Composer-Efforts-Light")
            app.buttons["reasoningOption:high"].tap()
            XCTAssertEqual(depth.label, "思考の深さ: 深い")
            XCTAssertTrue(app.keyboards.firstMatch.exists)
            input.tap()
            input.typeText("\nSecond line")
            XCTAssertGreaterThan(composer.frame.height, editingHeight)
            XCTAssertGreaterThanOrEqual(app.keyboards.firstMatch.frame.minY - composer.frame.maxY, 8)
            attachScreenshot(dark ? "Human-Composer-Two-Lines-Dark" : "Human-Composer-Two-Lines-Light")
            input.typeText("\nThird line")
            XCTAssertGreaterThan(composer.frame.height, editingHeight)
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.3)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertFalse(depth.exists)
            XCTAssertEqual(composer.frame.height, emptyHeight, accuracy: 1)
            XCTAssertEqual(input.value as? String, "First line\nSecond line\nThird line")
            send.tap()
            XCTAssertTrue(app.staticTexts["human-standard（深い）の回答です。"].waitForExistence(timeout: 10))
            XCTAssertEqual(composer.frame.height, emptyHeight, accuracy: 1)
            model.tap()
            app.buttons["modelOption:asuka-1.1"].tap()
            XCTAssertTrue(depth.waitForNonExistence(timeout: 5))
            XCTAssertEqual(composer.frame.height, compactHeight, accuracy: 1)
            app.terminate()
        }
    }
    func testOperationErrorsPreserveDraftWithoutStatusOrRetryUI() {
        let app = launchFixture("operation-errors")
        app.buttons["conversationMenu"].tap()
        app.buttons["newConversation"].tap()
        let composer = app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch
        let input = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
        let restingHeight = composer.frame.height
        input.tap()
        input.typeText("Keep this message")
        let send = app.buttons["sendMessage"]
        send.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
        XCTAssertEqual(input.value as? String, "Keep this message")
        XCTAssertTrue(send.isEnabled)
        XCTAssertEqual(composer.frame.height, restingHeight, accuracy: 1)
        XCTAssertFalse(app.staticTexts["キャンセルしました"].exists)
        XCTAssertFalse(app.buttons["再試行"].exists)
        attachScreenshot("Chat-After-Cancelled-Request")

        app.buttons["conversationMenu"].tap()
        XCTAssertTrue(app.staticTexts["会話はまだありません。"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["キャンセルしました"].exists)
        app.buttons["sidebarAccount"].tap()
        XCTAssertTrue(app.buttons["signOut"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["開発用の確認"].exists)
        XCTAssertFalse(app.buttons["API認証を確認"].exists)
        XCTAssertFalse(app.staticTexts["接続を確認してください"].exists)
        attachScreenshot("Account-Without-Developer-Controls")
        app.buttons["閉じる"].tap()

        openBrain(app)
        let start = app.buttons["思考をはじめる"]
        XCTAssertTrue(start.waitForExistence(timeout: 5))
        start.tap()
        XCTAssertTrue(start.isEnabled)
        XCTAssertFalse(app.staticTexts["キャンセルしました"].exists)
        XCTAssertFalse(app.buttons["再試行"].exists)
        attachScreenshot("Brain-After-Cancelled-Request")
        app.buttons["conversationMenu"].tap()
        XCTAssertTrue(app.staticTexts["回答履歴はまだありません。"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["キャンセルしました"].exists)
    }
    func testSidebarSwipesPreserveDraft() {
        let app = launchFixture()
        let input = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
        input.tap()
        input.typeText("Keep this draft")
        let edge = app.coordinate(withNormalizedOffset: CGVector(dx: 0.01, dy: 0.45))
        let openPoint = app.coordinate(withNormalizedOffset: CGVector(dx: 0.8, dy: 0.45))
        edge.press(forDuration: 0.05, thenDragTo: openPoint)
        let switcher = app.buttons["productSwitcher"]
        XCTAssertTrue(switcher.waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(switcher.isHittable)
        XCTAssertTrue(switcher.label.contains("SodAI Chat"))
        attachScreenshot("Sidebar-Edge-Opened")
        XCTAssertFalse(input.isHittable)
        XCTAssertEqual(app.keyboards.count, 0)
        app.buttons["closeSidebar"].tap()
        XCTAssertTrue(input.waitForExistence(timeout: 5))
        XCTAssertTrue(input.isHittable)
        XCTAssertEqual(input.value as? String, "Keep this draft")

        // A right swipe also opens from the middle of the conversation.
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.25, dy: 0.45))
            .press(forDuration: 0.05, thenDragTo: openPoint)
        XCTAssertTrue(switcher.waitForExistence(timeout: 5))
        XCTAssertTrue(switcher.isHittable)
        app.buttons["closeSidebar"].tap()
        XCTAssertTrue(input.isHittable)
        XCTAssertEqual(input.value as? String, "Keep this draft")
        // Vertical scrolling must not open the sidebar.
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.6))
            .press(
                forDuration: 0.05,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.2)))
        XCTAssertFalse(switcher.isHittable)

        // Releasing a short, slow edge drag should settle back to the conversation.
        edge.press(
            forDuration: 0.05,
            thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.15, dy: 0.45)),
            withVelocity: .slow, thenHoldForDuration: 0.4)
        XCTAssertFalse(switcher.isHittable)

        app.buttons["conversationMenu"].tap()
        XCTAssertTrue(switcher.waitForExistence(timeout: 5))
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.7, dy: 0.4))
            .press(
                forDuration: 0.05,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.05, dy: 0.4)))
        XCTAssertTrue(input.waitForExistence(timeout: 5))
        XCTAssertTrue(input.isHittable)
        XCTAssertEqual(input.value as? String, "Keep this draft")
    }

    func testComposerFocusAndOutsideDismissal() {
        for dark in [false, true] {
            let app = launchFixture("sidebar", dark: dark)
            app.buttons["conversationMenu"].tap()
            app.buttons["newConversation"].tap()
            let composer = app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch
            let input = app.descendants(matching: .any).matching(identifier: "messageInput").firstMatch
            let restingBottom = composer.frame.maxY
            let restingHeight = composer.frame.height
            let singleTextLineHeight = input.frame.height
            XCTAssertEqual(input.frame.midY, composer.frame.midY, accuracy: 1)
            // The leading inset belongs to the composer, outside the text editor.
            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.03, dy: 0.5)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            let focusedHeight = composer.frame.height
            XCTAssertGreaterThan(focusedHeight, restingHeight)
            XCTAssertEqual(input.frame.height, singleTextLineHeight, accuracy: 1)
            input.typeText("Keep this draft")
            XCTAssertEqual(composer.frame.height, focusedHeight, accuracy: 1)
            XCTAssertLessThanOrEqual(input.frame.maxY, app.buttons["sendMessage"].frame.minY)
            XCTAssertEqual(app.buttons["sendMessage"].frame.maxY, composer.frame.maxY - 8, accuracy: 1)
            // Keyboard accessibility bounds can exclude the background's top inset.
            XCTAssertGreaterThanOrEqual(app.keyboards.firstMatch.frame.minY - composer.frame.maxY, 8)
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.3)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertEqual(composer.frame.maxY, restingBottom, accuracy: 1)
            XCTAssertEqual(composer.frame.height, restingHeight, accuracy: 1)
            XCTAssertEqual(input.value as? String, "Keep this draft")

            // The lower inset focuses too; tapping actual text must keep editing.
            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.95)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            XCTAssertEqual(composer.frame.height, focusedHeight, accuracy: 1)
            input.tap()
            XCTAssertTrue(app.keyboards.firstMatch.exists)
            attachScreenshot(dark ? "Glass-Composer-Editing-Dark" : "Glass-Composer-Editing-Light")

            // Toolbar controls must still work on the first tap while editing.
            app.buttons["modelPicker"].tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertTrue(app.buttons["humanModels"].waitForExistence(timeout: 5))
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.55)).tap()

            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.03, dy: 0.5)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            app.buttons["sendMessage"].tap()
            XCTAssertTrue(app.staticTexts["Keep this draft"].waitForExistence(timeout: 10))
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))

            app.buttons["conversationMenu"].tap()
            app.buttons["threadRow:sidebar-thread-1"].tap()
            let scroll = app.scrollViews["conversationScroll"]
            XCTAssertTrue(scroll.waitForExistence(timeout: 5))
            scroll.swipeDown()
            attachScreenshot(dark ? "Glass-Composer-Over-Content-Dark" : "Glass-Composer-Over-Content-Light")
            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.03, dy: 0.5)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            input.typeText("Still here")
            let oneTextLineHeight = composer.frame.height
            input.typeText("\nSecond line")
            XCTAssertGreaterThan(composer.frame.height, oneTextLineHeight)
            XCTAssertGreaterThanOrEqual(app.keyboards.firstMatch.frame.minY - composer.frame.maxY, 8)
            attachScreenshot(dark ? "Glass-Composer-Multiline-Dark" : "Glass-Composer-Multiline-Light")
            let twoTextLineHeight = composer.frame.height
            input.typeText("\nThird line")
            XCTAssertGreaterThan(composer.frame.height, twoTextLineHeight)
            // Dismiss on message text as well as the narrow margin beside the glass.
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.35)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertEqual(composer.frame.height, restingHeight, accuracy: 1)
            composer.coordinate(withNormalizedOffset: CGVector(dx: 0.03, dy: 0.5)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
            app.coordinate(withNormalizedOffset: .zero)
                .withOffset(CGVector(dx: 5, dy: composer.frame.midY)).tap()
            XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5))
            XCTAssertEqual(input.value as? String, "Still here\nSecond line\nThird line")
            XCTAssertEqual(composer.frame.height, restingHeight, accuracy: 1)
            app.terminate()
        }
    }

    func testSidebarProductsAndAccount() {
        for dark in [false, true] {
            let app = launchFixture(dark: dark)
            openBrain(app)
            app.buttons["conversationMenu"].tap()
            let switcher = app.buttons["productSwitcher"]
            XCTAssertTrue(switcher.label.contains("SodAI Brain"))
            XCTAssertTrue(app.staticTexts["回答履歴"].exists)
            attachScreenshot("Sidebar-Brain")
            switcher.tap()
            attachScreenshot("Sidebar-Product-Switcher")
            app.buttons["switchChat"].tap()
            attachScreenshot(dark ? "Sidebar-Chat-Switched-Dark" : "Sidebar-Chat-Switched-Light")
            XCTAssertTrue(switcher.label.contains("SodAI Chat"))
            XCTAssertTrue(app.buttons["newConversation"].exists)
            app.buttons["sidebarAccount"].tap()
            XCTAssertTrue(app.buttons["閉じる"].waitForExistence(timeout: 5))
            app.buttons["閉じる"].tap()
            XCTAssertTrue(app.buttons["conversationMenu"].waitForExistence(timeout: 5))
            app.terminate()
        }
    }
    func testSidebarChromeAlignmentInBothAppearances() {
        for dark in [false, true] {
            let app = launchFixture("sidebar", dark: dark)
            let composer = app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch
            XCTAssertTrue(composer.waitForExistence(timeout: 5))
            let headerY = app.buttons["conversationMenu"].frame.midY
            let composerY = composer.frame.midY
            XCTAssertFalse(app.buttons["accountMenu"].exists)
            app.buttons["conversationMenu"].tap()
            let switcher = app.buttons["productSwitcher"]
            XCTAssertTrue(switcher.waitForExistence(timeout: 5))
            attachScreenshot(dark ? "Aligned-Sidebar-Dark" : "Aligned-Sidebar-Light")
            XCTAssertEqual(
                app.buttons["threadRow:sidebar-thread-1"].frame.height,
                app.buttons["threadRow:sidebar-thread-2"].frame.height, accuracy: 1)
            XCTAssertEqual(switcher.frame.midY, headerY, accuracy: 1)
            XCTAssertEqual(app.buttons["toggleThreadSearch"].frame.midY, headerY, accuracy: 1)
            XCTAssertEqual(app.buttons["newConversation"].frame.midY, composerY, accuracy: 1)
            XCTAssertEqual(app.buttons["sidebarAccount"].frame.midY, composerY, accuracy: 1)
            app.buttons["closeSidebar"].tap()
            XCTAssertTrue(app.buttons["conversationMenu"].isHittable)
            app.terminate()
        }
    }
    func testSidebarDarkAppearanceAndHistoryScroll() {
        let app = launchFixture("sidebar", dark: true)
        app.buttons["conversationMenu"].tap()
        XCTAssertTrue(app.buttons["threadRow:sidebar-thread-1"].waitForExistence(timeout: 5))
        let headerFrame = app.buttons["productSwitcher"].frame
        let footerFrame = app.buttons["newConversation"].frame
        attachScreenshot("Sidebar-Dark-History")
        let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.8))
        let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.25))
        start.press(forDuration: 0.05, thenDragTo: end)
        start.press(forDuration: 0.05, thenDragTo: end)
        XCTAssertEqual(app.buttons["productSwitcher"].frame, headerFrame)
        XCTAssertEqual(app.buttons["newConversation"].frame, footerFrame)
        XCTAssertTrue(app.buttons["newConversation"].isHittable)
        XCTAssertFalse(app.buttons["threadRow:sidebar-thread-1"].isHittable)
        attachScreenshot("Sidebar-Dark-Scrolled")
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.7, dy: 0.4))
            .press(
                forDuration: 0.05,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.05, dy: 0.4)))
        XCTAssertTrue(app.buttons["conversationMenu"].waitForExistence(timeout: 5))
    }
    func testSidebarSwipeOverLongConversation() {
        let app = launchFixture("sidebar")
        app.buttons["conversationMenu"].tap()
        app.buttons["threadRow:sidebar-thread-1"].tap()
        let response = app.descendants(matching: .any).matching(identifier: "assistantMessage").firstMatch
        XCTAssertTrue(response.waitForExistence(timeout: 5))
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5))
            .press(
                forDuration: 0.05,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5)))
        XCTAssertTrue(app.buttons["productSwitcher"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["productSwitcher"].isHittable)
        app.buttons["closeSidebar"].tap()
        XCTAssertTrue(response.waitForExistence(timeout: 5))
        app.buttons["conversationMenu"].tap()
        app.buttons["newConversation"].tap()
        XCTAssertTrue(app.scrollViews["conversationScroll"].waitForNonExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["こんにちは。"].exists)
        let composerFrame = app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch
            .frame
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.6))
            .press(
                forDuration: 0.05,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.3)))
        XCTAssertFalse(app.scrollViews["conversationScroll"].exists)
        XCTAssertEqual(
            app.descendants(matching: .any).matching(identifier: "messageComposer").firstMatch.frame,
            composerFrame)
        attachScreenshot("New-Conversation-After-Scroll")
    }
    func testBrainAnswerAndFrozenHistory() {
        let app = launchFixture()
        openBrain(app)
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 10), app.debugDescription)
        attachScreenshot("Brain-Lobby")
        app.buttons["思考をはじめる"].tap()
        let input = app.descendants(matching: .any).matching(identifier: "brainAnswerInput").firstMatch
        XCTAssertTrue(input.waitForExistence(timeout: 10), app.debugDescription)
        input.tap()
        input.typeText("Good morning. Have a nice day.")
        app.buttons["送信"].tap()
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 10))
        app.buttons["conversationMenu"].tap()
        let history = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "朝の挨拶を教えてください。"))
            .firstMatch
        XCTAssertTrue(history.waitForExistence(timeout: 10), app.debugDescription)
        history.tap()
        XCTAssertTrue(
            app.staticTexts["Good morning. Have a nice day."].waitForExistence(timeout: 10),
            app.debugDescription)
        attachScreenshot("Brain-History")
    }
    func testBrainWaitingCanStopAndDeclineRequiresConfirmation() {
        let app = launchFixture("waiting")
        openBrain(app)
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 10))
        app.buttons["思考をはじめる"].tap()
        XCTAssertTrue(app.buttons["待機をやめる"].waitForExistence(timeout: 10))
        attachScreenshot("Brain-Waiting")
        app.buttons["待機をやめる"].tap()
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 10))
        app.terminate()
        app.launchArguments = ["-platform-ui-fixture", "assigned"]
        app.launch()
        openBrain(app)
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 10))
        app.buttons["思考をはじめる"].tap()
        XCTAssertTrue(app.buttons["辞退する"].waitForExistence(timeout: 10))
        attachScreenshot("Brain-Assignment")
        app.buttons["辞退する"].tap()
        XCTAssertTrue(app.buttons["キャンセル"].waitForExistence(timeout: 5))
        app.buttons["キャンセル"].tap()
        XCTAssertTrue(
            app.descendants(matching: .any).matching(identifier: "brainAnswerInput").firstMatch
                .waitForExistence(timeout: 5))
        app.buttons["辞退する"].tap()
        XCTAssertTrue(app.alerts.buttons["辞退する"].waitForExistence(timeout: 5))
        app.alerts.buttons["辞退する"].tap()
        XCTAssertTrue(app.buttons["待機をやめる"].waitForExistence(timeout: 5))
    }
    func testProductionScreensReadOnly() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["SODAI_LIVE_INTEGRATION"] == "1")
        let app = XCUIApplication()
        app.launchArguments = []
        app.launch()
        XCTAssertTrue(app.buttons["conversationMenu"].waitForExistence(timeout: 15))
        attachScreenshot("Production-Chat")
        openBrain(app)
        XCTAssertTrue(app.buttons["思考をはじめる"].waitForExistence(timeout: 20), app.debugDescription)
        attachScreenshot("Production-Brain")
    }
    private func openBrain(_ app: XCUIApplication) {
        app.buttons["conversationMenu"].tap()
        let switcher = app.buttons["productSwitcher"]
        XCTAssertTrue(switcher.waitForExistence(timeout: 10))
        switcher.tap()
        let brain = app.buttons["switchBrain"]
        XCTAssertTrue(brain.waitForExistence(timeout: 5), app.debugDescription)
        brain.tap()
        app.buttons["closeSidebar"].tap()
    }
    private func attachScreenshot(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}

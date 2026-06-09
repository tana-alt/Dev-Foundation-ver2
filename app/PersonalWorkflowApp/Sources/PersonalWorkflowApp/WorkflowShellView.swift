import AppKit

final class WorkflowShellView: NSView {
    private let fixture: WorkflowFixture

    init(fixture: WorkflowFixture) {
        self.fixture = fixture
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false
        wantsLayer = true
        layer?.backgroundColor = Palette.window.cgColor
        buildLayout()
    }

    required init?(coder: NSCoder) {
        nil
    }

    private func buildLayout() {
        let root = NSStackView()
        root.orientation = .vertical
        root.spacing = 0
        root.translatesAutoresizingMaskIntoConstraints = false
        addSubview(root)

        root.addArrangedSubview(makeToolbar())
        root.addArrangedSubview(separator())
        root.addArrangedSubview(makeWorkspace())
        root.addArrangedSubview(separator())
        root.addArrangedSubview(makeGateStrip())

        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: leadingAnchor),
            root.trailingAnchor.constraint(equalTo: trailingAnchor),
            root.topAnchor.constraint(equalTo: topAnchor),
            root.bottomAnchor.constraint(equalTo: bottomAnchor)
        ])
    }

    private func makeToolbar() -> NSView {
        let bar = NSStackView()
        bar.orientation = .horizontal
        bar.alignment = .centerY
        bar.spacing = 14
        bar.edgeInsets = NSEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)
        bar.wantsLayer = true
        bar.layer?.backgroundColor = Palette.chrome.cgColor

        bar.addArrangedSubview(title("Personal Workflow", size: 14, weight: .semibold))
        let stageLabels: [String] = WorkflowStage.allCases.map { $0.label }
        let segmented = NSSegmentedControl(
            labels: stageLabels,
            trackingMode: .selectOne,
            target: nil,
            action: nil
        )
        segmented.selectedSegment = 1
        segmented.widthAnchor.constraint(equalToConstant: 520).isActive = true
        bar.addArrangedSubview(segmented)
        bar.addArrangedSubview(spacer())
        bar.addArrangedSubview(pill("CommonDB", "dry_run", .complete))
        bar.addArrangedSubview(pill("Scope", "guarded", .active))

        let button = NSButton(title: "Open Codex Ref", target: self, action: #selector(openCodexApp))
        button.bezelStyle = .rounded
        button.contentTintColor = Palette.blue
        bar.addArrangedSubview(button)
        return bar
    }

    private func makeWorkspace() -> NSView {
        let workspace = NSStackView()
        workspace.orientation = .horizontal
        workspace.spacing = 0

        let left = makeLeftPanel()
        left.widthAnchor.constraint(equalToConstant: 282).isActive = true
        workspace.addArrangedSubview(left)
        workspace.addArrangedSubview(verticalSeparator())
        workspace.addArrangedSubview(makeCenterTabs())
        workspace.addArrangedSubview(verticalSeparator())

        let inspector = makeInspector()
        inspector.widthAnchor.constraint(equalToConstant: 330).isActive = true
        workspace.addArrangedSubview(inspector)
        return workspace
    }

    private func makeCenterTabs() -> NSView {
        let tabs = NSTabView()
        tabs.tabViewType = .topTabsBezelBorder
        tabs.addTabViewItem(tabItem(label: "Board", view: makeLaneMap()))
        tabs.addTabViewItem(tabItem(label: "Repository", view: makeRepositoryWorktreeClosePage()))
        return tabs
    }

    private func tabItem(label: String, view: NSView) -> NSTabViewItem {
        let item = NSTabViewItem(identifier: label)
        item.label = label
        item.view = view
        return item
    }

    private func makeLeftPanel() -> NSView {
        let panel = verticalPanel(background: Palette.sidebar)
        panel.addArrangedSubview(sectionHeader("Goal Outline"))
        fixture.goals.forEach { panel.addArrangedSubview(goalRow($0)) }
        panel.addArrangedSubview(separator())
        panel.addArrangedSubview(sectionHeader("Source Refs"))
        fixture.sourceReferences.forEach { panel.addArrangedSubview(sourceRow($0)) }
        panel.addArrangedSubview(spacer())
        return panel
    }

    private func makeLaneMap() -> NSView {
        let outer = verticalPanel(background: Palette.content)
        let header = NSStackView()
        header.orientation = .horizontal
        header.alignment = .centerY
        header.addArrangedSubview(title("Lane Map", size: 18, weight: .semibold))
        header.addArrangedSubview(spacer())
        header.addArrangedSubview(pill("View", "Board", .active))
        outer.addArrangedSubview(header)
        outer.addArrangedSubview(caption("Board view with worker boundaries, cross-review, and handoff gates."))

        let scroll = NSScrollView()
        scroll.hasHorizontalScroller = true
        scroll.hasVerticalScroller = false
        scroll.borderType = .noBorder
        let lanes = NSStackView()
        lanes.orientation = .horizontal
        lanes.alignment = .top
        lanes.spacing = 12
        LaneKind.allCases.forEach { lane in
            let column = laneColumn(lane: lane, cards: fixture.laneCards.filter { $0.lane == lane })
            column.widthAnchor.constraint(equalToConstant: 235).isActive = true
            lanes.addArrangedSubview(column)
        }
        scroll.documentView = lanes
        outer.addArrangedSubview(scroll)
        return outer
    }

    private func makeRepositoryWorktreeClosePage() -> NSView {
        let outer = verticalPanel(background: Palette.content)
        let header = NSStackView()
        header.orientation = .horizontal
        header.alignment = .centerY
        header.addArrangedSubview(title("Repository", size: 18, weight: .semibold))
        header.addArrangedSubview(spacer())
        header.addArrangedSubview(pill("Tab", "Worktree close", .active))
        outer.addArrangedSubview(header)
        outer.addArrangedSubview(caption("Close candidates are grouped by repository and gated by PR state, active session, and local-only work."))

        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.borderType = .noBorder

        let list = verticalPanel(background: Palette.content)
        list.spacing = 12
        fixture.worktreeCloseCandidates.forEach { candidate in
            list.addArrangedSubview(worktreeCloseCard(candidate))
        }
        list.addArrangedSubview(spacer())
        scroll.documentView = list
        outer.addArrangedSubview(scroll)
        return outer
    }

    private func worktreeCloseCard(_ candidate: WorktreeCloseCandidate) -> NSView {
        let card = verticalPanel(background: Palette.card)
        card.layer?.borderColor = statusColor(candidate.closeState).withAlphaComponent(0.55).cgColor
        card.layer?.borderWidth = 1

        let header = NSStackView()
        header.orientation = .horizontal
        header.alignment = .centerY
        header.addArrangedSubview(title(candidate.repositoryName, size: 14, weight: .semibold))
        header.addArrangedSubview(spacer())
        header.addArrangedSubview(pill("Close", candidate.closeState.rawValue, candidate.closeState))
        card.addArrangedSubview(header)

        card.addArrangedSubview(caption(candidate.worktreePath))
        card.addArrangedSubview(statusBlock("Pull Request", candidate.pullRequest, .complete))
        let activeSessionLabel = candidate.activeSession ? "Active" : "None"
        let activeSessionStatus = statusForActiveSession(candidate.activeSession)
        let localHeadStatus = statusForLocalPRHead(candidate.localPRHeadStatus)
        let untrackedStatus = statusForUntrackedPolicy(candidate.untrackedPolicy)

        card.addArrangedSubview(statusBlock("Active Session", activeSessionLabel, activeSessionStatus))
        card.addArrangedSubview(statusBlock("Local PR Head", candidate.localPRHeadStatus.rawValue, localHeadStatus))
        card.addArrangedSubview(statusBlock("Untracked", candidate.untrackedPolicy.rawValue, untrackedStatus))
        card.addArrangedSubview(infoBlock("Close Reason", candidate.closeReason))

        let actions = NSStackView()
        actions.orientation = .horizontal
        actions.alignment = .centerY
        actions.spacing = 8
        actions.addArrangedSubview(spacer())
        let review = NSButton(title: "Review Close", target: self, action: #selector(mockReviewClose))
        review.bezelStyle = .rounded
        actions.addArrangedSubview(review)
        let close = NSButton(title: "Close Worktree", target: self, action: #selector(mockReviewClose))
        close.bezelStyle = .rounded
        close.isEnabled = candidate.closeState == .ready
        actions.addArrangedSubview(close)
        card.addArrangedSubview(actions)
        return card
    }

    private func makeInspector() -> NSView {
        let panel = verticalPanel(background: Palette.inspector)
        panel.addArrangedSubview(sectionHeader("Approvals / CommonDB"))
        fixture.approvals.forEach { panel.addArrangedSubview(approvalRow($0)) }
        panel.addArrangedSubview(separator())
        panel.addArrangedSubview(sectionHeader("Implemented Checks"))
        fixture.integrationChecks.forEach { check in
            panel.addArrangedSubview(statusBlock(check.title, check.detail, check.status))
        }
        panel.addArrangedSubview(infoBlock("Codex Link Ref", safeCodexLinkDescription()))
        panel.addArrangedSubview(infoBlock("useful_source", fixture.usefulSource))
        panel.addArrangedSubview(infoBlock("approved_memo", fixture.approvedMemo))
        panel.addArrangedSubview(infoBlock("Scope Guard", fixture.scopeGuardItems.joined(separator: "\n")))
        panel.addArrangedSubview(spacer())

        let button = NSButton(title: "Open Codex Ref", target: self, action: #selector(openCodexApp))
        button.bezelStyle = .rounded
        panel.addArrangedSubview(button)
        return panel
    }

    private func makeGateStrip() -> NSView {
        let strip = NSStackView()
        strip.orientation = .horizontal
        strip.alignment = .centerY
        strip.spacing = 10
        strip.edgeInsets = NSEdgeInsets(top: 10, left: 18, bottom: 10, right: 18)
        strip.wantsLayer = true
        strip.layer?.backgroundColor = Palette.chrome.cgColor
        strip.addArrangedSubview(caption("Contract / Verification / Gate"))
        fixture.gateChecks.forEach { strip.addArrangedSubview(pill($0.title, $0.state, $0.status)) }
        strip.addArrangedSubview(spacer())
        strip.addArrangedSubview(caption("Fixture shell plus implemented local checks. No live CommonDB/Qdrant or raw bodies."))
        return strip
    }

    private func laneColumn(lane: LaneKind, cards: [LaneCard]) -> NSView {
        let column = verticalPanel(background: Palette.lane)
        column.layer?.borderColor = laneColor(lane).withAlphaComponent(0.55).cgColor
        column.layer?.borderWidth = lane == .mainLane ? 2 : 1
        column.addArrangedSubview(title("\(lane.title)  \(cards.count)", size: 12, weight: .semibold))
        cards.forEach { column.addArrangedSubview(laneCard($0)) }
        column.addArrangedSubview(spacer())
        return column
    }

    private func laneCard(_ card: LaneCard) -> NSView {
        let cardView = verticalPanel(background: Palette.card)
        cardView.addArrangedSubview(title(card.title, size: 13, weight: .semibold))
        cardView.addArrangedSubview(caption(card.summary))
        cardView.addArrangedSubview(caption("\(card.owner)  •  \(card.status.rawValue)"))
        cardView.addArrangedSubview(caption(card.gates.map { "#\($0)" }.joined(separator: "  ")))
        return cardView
    }

    private func goalRow(_ goal: GoalNode) -> NSView {
        statusBlock(goal.title, "\(goal.childCount) linked items", goal.status)
    }

    private func sourceRow(_ source: SourceReference) -> NSView {
        statusBlock(source.title, source.detail, source.isAvailable ? .complete : .waiting)
    }

    private func statusForActiveSession(_ activeSession: Bool) -> WorkItemStatus {
        activeSession ? .blocked : .complete
    }

    private func statusForLocalPRHead(_ status: LocalPRHeadStatus) -> WorkItemStatus {
        switch status {
        case .matchesPRBranch:
            return .complete
        case .localAheadPRBranch:
            return .blocked
        case .unknown:
            return .waiting
        }
    }

    private func statusForUntrackedPolicy(_ policy: UntrackedPolicy) -> WorkItemStatus {
        switch policy {
        case .none:
            return .complete
        case .reviewBeforeClose:
            return .waiting
        }
    }

    private func approvalRow(_ record: ApprovalRecord) -> NSView {
        statusBlock(record.label, record.value, record.state)
    }

    private func infoBlock(_ heading: String, _ body: String) -> NSView {
        let block = verticalPanel(background: Palette.panel)
        block.addArrangedSubview(title(heading, size: 12, weight: .semibold))
        block.addArrangedSubview(caption(body))
        return block
    }

    private func statusBlock(_ heading: String, _ body: String, _ status: WorkItemStatus) -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.alignment = .top
        row.spacing = 9
        row.edgeInsets = NSEdgeInsets(top: 9, left: 9, bottom: 9, right: 9)
        row.wantsLayer = true
        row.layer?.backgroundColor = Palette.panel.cgColor
        row.layer?.cornerRadius = 7

        let dot = NSView()
        dot.wantsLayer = true
        dot.layer?.backgroundColor = statusColor(status).cgColor
        dot.layer?.cornerRadius = 4
        dot.widthAnchor.constraint(equalToConstant: 8).isActive = true
        dot.heightAnchor.constraint(equalToConstant: 8).isActive = true
        row.addArrangedSubview(dot)

        let textStack = NSStackView()
        textStack.orientation = .vertical
        textStack.spacing = 3
        textStack.addArrangedSubview(title(heading, size: 12, weight: .semibold))
        textStack.addArrangedSubview(caption(body))
        row.addArrangedSubview(textStack)
        return row
    }

    private func verticalPanel(background: NSColor) -> NSStackView {
        let panel = NSStackView()
        panel.orientation = .vertical
        panel.alignment = .leading
        panel.spacing = 10
        panel.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        panel.wantsLayer = true
        panel.layer?.backgroundColor = background.cgColor
        panel.layer?.cornerRadius = 8
        return panel
    }

    private func sectionHeader(_ text: String) -> NSTextField {
        title(text, size: 13, weight: .semibold)
    }

    private func title(_ text: String, size: CGFloat, weight: NSFont.Weight) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.font = .systemFont(ofSize: size, weight: weight)
        field.textColor = .labelColor
        field.lineBreakMode = .byTruncatingTail
        field.maximumNumberOfLines = 2
        return field
    }

    private func caption(_ text: String) -> NSTextField {
        let field = NSTextField(wrappingLabelWithString: text)
        field.font = .systemFont(ofSize: 11)
        field.textColor = .secondaryLabelColor
        field.maximumNumberOfLines = 4
        return field
    }

    private func pill(_ title: String, _ value: String, _ status: WorkItemStatus) -> NSView {
        let pill = NSStackView()
        pill.orientation = .horizontal
        pill.alignment = .centerY
        pill.spacing = 6
        pill.edgeInsets = NSEdgeInsets(top: 5, left: 9, bottom: 5, right: 9)
        pill.wantsLayer = true
        pill.layer?.backgroundColor = Palette.panel.cgColor
        pill.layer?.cornerRadius = 12

        let dot = NSView()
        dot.wantsLayer = true
        dot.layer?.backgroundColor = statusColor(status).cgColor
        dot.layer?.cornerRadius = 3.5
        dot.widthAnchor.constraint(equalToConstant: 7).isActive = true
        dot.heightAnchor.constraint(equalToConstant: 7).isActive = true
        pill.addArrangedSubview(dot)
        pill.addArrangedSubview(caption(title))
        pill.addArrangedSubview(caption(value))
        return pill
    }

    private func spacer() -> NSView {
        let view = NSView()
        view.setContentHuggingPriority(.defaultLow, for: .horizontal)
        view.setContentHuggingPriority(.defaultLow, for: .vertical)
        return view
    }

    private func separator() -> NSView {
        let view = NSBox()
        view.boxType = .separator
        return view
    }

    private func verticalSeparator() -> NSView {
        let view = NSView()
        view.wantsLayer = true
        view.layer?.backgroundColor = Palette.border.cgColor
        view.widthAnchor.constraint(equalToConstant: 1).isActive = true
        return view
    }

    private func safeCodexLinkDescription() -> String {
        if isSafeOpaqueCodexURL(fixture.codexDeepLinkURL) {
            return "Ready: codex scheme with opaque safe ref only."
        }
        return "Blocked: link must use a local codex:// ref without secret or raw markers."
    }

    private func isSafeOpaqueCodexURL(_ url: URL) -> Bool {
        guard url.scheme == "codex" else {
            return false
        }
        let absolute = url.absoluteString.lowercased()
        let forbiddenMarkers = ["token", "secret", "password", "raw", "/users/", "file://", "http://", "https://"]
        return !forbiddenMarkers.contains { absolute.contains($0) }
    }

    @objc private func openCodexApp() {
        guard isSafeOpaqueCodexURL(fixture.codexDeepLinkURL) else {
            NSSound.beep()
            return
        }
        NSWorkspace.shared.open(fixture.codexDeepLinkURL)
    }

    @objc private func mockReviewClose() {
        NSSound.beep()
    }
}

private enum Palette {
    static let window = NSColor.windowBackgroundColor
    static let chrome = NSColor.controlBackgroundColor
    static let sidebar = NSColor.underPageBackgroundColor
    static let content = NSColor.textBackgroundColor
    static let inspector = NSColor.controlBackgroundColor
    static let panel = NSColor.windowBackgroundColor.withAlphaComponent(0.76)
    static let lane = NSColor.controlBackgroundColor.withAlphaComponent(0.68)
    static let card = NSColor.textBackgroundColor
    static let border = NSColor.separatorColor
    static let blue = NSColor.systemBlue
    static let green = NSColor.systemGreen
    static let amber = NSColor.systemOrange
    static let red = NSColor.systemRed
    static let purple = NSColor.systemPurple
}

private func statusColor(_ status: WorkItemStatus) -> NSColor {
    switch status {
    case .ready:
        return .secondaryLabelColor
    case .active:
        return Palette.blue
    case .waiting:
        return Palette.amber
    case .blocked:
        return Palette.red
    case .complete:
        return Palette.green
    }
}

private func laneColor(_ lane: LaneKind) -> NSColor {
    switch lane {
    case .mainLane:
        return Palette.blue
    case .subagent:
        return Palette.green
    case .review:
        return Palette.amber
    case .handoff:
        return Palette.purple
    }
}

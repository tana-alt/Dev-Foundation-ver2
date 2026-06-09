import Foundation

enum WorkflowStage: String, CaseIterable, Identifiable {
    case setup = "Setup"
    case board = "Board"
    case review = "Review"
    case archive = "Archive"

    var id: String { rawValue }

    var label: String { rawValue }
}

enum LaneKind: String, CaseIterable, Identifiable {
    case mainLane = "main_lane"
    case subagent = "subagent"
    case review = "review"
    case handoff = "handoff"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .mainLane: "main_lane"
        case .subagent: "Subagents"
        case .review: "Review"
        case .handoff: "Handoff"
        }
    }
}

enum WorkItemStatus: String {
    case ready = "Ready"
    case active = "Active"
    case waiting = "Waiting"
    case blocked = "Blocked"
    case complete = "Complete"
}

struct GoalNode: Identifiable {
    let id = UUID()
    let title: String
    let status: WorkItemStatus
    let childCount: Int
}

struct SourceReference: Identifiable {
    let id = UUID()
    let title: String
    let detail: String
    let isAvailable: Bool
}

struct LaneCard: Identifiable {
    let id = UUID()
    let lane: LaneKind
    let title: String
    let summary: String
    let owner: String
    let status: WorkItemStatus
    let gates: [String]
}

struct GateCheck: Identifiable {
    let id = UUID()
    let title: String
    let state: String
    let status: WorkItemStatus
}

struct ApprovalRecord: Identifiable {
    let id = UUID()
    let label: String
    let value: String
    let state: WorkItemStatus
}

struct WorkflowFixture {
    let goals: [GoalNode]
    let sourceReferences: [SourceReference]
    let laneCards: [LaneCard]
    let gateChecks: [GateCheck]
    let approvals: [ApprovalRecord]
    let usefulSource: String
    let approvedMemo: String
    let scopeGuardItems: [String]

    static let preview = WorkflowFixture(
        goals: [
            GoalNode(title: "Personal Mac Workflow App", status: .active, childCount: 4),
            GoalNode(title: "Swift Package shell", status: .complete, childCount: 2),
            GoalNode(title: "CommonDB approval model", status: .waiting, childCount: 3),
            GoalNode(title: "Codex handoff action", status: .ready, childCount: 1)
        ],
        sourceReferences: [
            SourceReference(
                title: "App spec",
                detail: "artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md",
                isAvailable: false
            ),
            SourceReference(
                title: "Direction B",
                detail: "artifact/workflow-ui-commondb-20260608/output/designs/personal-mac-workflow-app-direction-b.png",
                isAvailable: false
            ),
            SourceReference(
                title: "Worker packet",
                detail: "Current scoped request, sanitized into mock fixtures",
                isAvailable: true
            )
        ],
        laneCards: [
            LaneCard(
                lane: .mainLane,
                title: "Shape approved scope",
                summary: "Holds the canonical goal, named refs, denied context, and write boundary.",
                owner: "main_lane",
                status: .active,
                gates: ["scope", "source_refs"]
            ),
            LaneCard(
                lane: .mainLane,
                title: "Dispatch worker packet",
                summary: "Routes UI shell implementation without exposing raw thread bodies.",
                owner: "main_lane",
                status: .complete,
                gates: ["allowed paths"]
            ),
            LaneCard(
                lane: .subagent,
                title: "Build SwiftUI shell",
                summary: "Creates native macOS layout with segmented stage control and lane map.",
                owner: "build worker",
                status: .active,
                gates: ["swift build"]
            ),
            LaneCard(
                lane: .subagent,
                title: "Fixture data only",
                summary: "Uses representative goals, refs, approvals, and gates without secrets.",
                owner: "build worker",
                status: .ready,
                gates: ["no raw bodies"]
            ),
            LaneCard(
                lane: .review,
                title: "Verify contract strip",
                summary: "Checks gate visibility, residual risk, and useful_source / approved_memo fields.",
                owner: "review lane",
                status: .waiting,
                gates: ["UI review"]
            ),
            LaneCard(
                lane: .handoff,
                title: "Send to Codex App",
                summary: "Packages safe context for a local app handoff action.",
                owner: "handoff",
                status: .ready,
                gates: ["human approval"]
            )
        ],
        gateChecks: [
            GateCheck(title: "Contract", state: "scoped", status: .active),
            GateCheck(title: "Verification", state: "build pending", status: .waiting),
            GateCheck(title: "Gate", state: "human review", status: .waiting),
            GateCheck(title: "Secrets", state: "excluded", status: .complete)
        ],
        approvals: [
            ApprovalRecord(label: "useful_source", value: "Worker packet and named refs", state: .waiting),
            ApprovalRecord(label: "approved_memo", value: "UI shell may use mock workflow data only", state: .complete),
            ApprovalRecord(label: "scope_guard", value: "app/PersonalWorkflowApp/**", state: .active)
        ],
        usefulSource: "Current worker packet plus source-ref placeholders. Raw thread bodies, credentials, browser state, and runtime logs are excluded.",
        approvedMemo: "Approved to implement a mock native macOS shell. CommonDB fields are represented as safe fixture values for review.",
        scopeGuardItems: [
            "Write only under app/PersonalWorkflowApp/**",
            "Do not touch Python workflow console files",
            "No raw thread bodies or secrets in fixtures",
            "Human gate required before any external write"
        ]
    )
}

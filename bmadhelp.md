# BMAD Help Reference

Welcome to the **BMad Method** help system. Below is a comprehensive reference of all available workflows, commands, and agents organized by module and phase.

> 💡 **Agent Switching**: Most workflows require specific agents. Use `*agent <agent-name>` to switch context before running workflows.

---

## 🎭 Agent Overview

| Agent | Role | Primary Workflows |
|-------|------|-------------------|
| **architect** | Design & Planning | PRD, Architecture, UX, Epics/Stories |
| **scrum-master** | Sprint Management | Sprint Planning, Status, Create Story |
| **dev** | Implementation | Dev Story, Code Review, QA |
| **tech-writer** | Documentation | Write/Validate Docs, Explain Concepts |
| **default** | General Tasks | Research, Quick Dev/Spec, Diagrams |

---

## 🏗️ BMB (Build Module Builder)
**Module for creating and managing BMAD components**

🎭 **Agent**: `default` (most workflows)

### Anytime Workflows
- **Create Agent** (`CA` | `bmad_bmb_agent`) - Create new BMAD agents with best practices
- **Edit Agent** (`EA` | `bmad_bmb_agent`) - Edit existing BMAD agents while maintaining compliance
- **Validate Agent** (`VA` | `bmad_bmb_agent`) - Validate existing BMAD agents and offer improvements
- **Create Module Brief** (`PB` | `bmad_bmb_module`) - Create product brief for BMAD module development
- **Create Module** (`CM` | `bmad_bmb_module`) - Create complete BMAD module with agents, workflows, and infrastructure
- **Edit Module** (`EM` | `bmad_bmb_module`) - Edit existing BMAD modules while maintaining coherence
- **Validate Module** (`VM` | `bmad_bmb_module`) - Run compliance check on BMAD modules
- **Create Workflow** (`CW` | `bmad_bmb_workflow`) - Create new BMAD workflow with proper structure
- **Edit Workflow** (`EW` | `bmad_bmb_workflow`) - Edit existing BMAD workflows while maintaining integrity
- **Validate Workflow** (`VW` | `bmad_bmb_workflow`) - Run validation check on BMAD workflows
- **Max Parallel Validate** (`MV` | `bmad_bmb_workflow`) - Run validation checks in MAX-PARALLEL mode
- **Rework Workflow** (`RW` | `bmad_bmb_workflow`) - Rework a Workflow to V6 compliant version

---

## 💼 BMM (BMAD Method Manager)
**Full-featured software development lifecycle management**

### Phase 1: Analysis
🎭 **Agent**: `default` or `architect`

- **Brainstorm Project** (`BP` | `bmad-brainstorming`) - Expert guided facilitation through brainstorming techniques
- **Market Research** (`MR` | `bmad-bmm-research`) - Market analysis, competitive landscape, customer needs and trends
- **Domain Research** (`DR` | `bmad-bmm-research`) - Industry domain deep dive, subject matter expertise and terminology
- **Technical Research** (`TR` | `bmad-bmm-research`) - Technical feasibility, architecture options and implementation approaches
- **Create Brief** (`CB` | `bmad-bmm-create-brief`) 🎭 `architect` - Guided experience to nail down your product idea
- **Validate Brief** (`VB` | `bmad-bmm-validate-brief`) 🎭 `architect` - Validates product brief completeness

### Phase 2: Planning
🎭 **Agent**: `architect` (required for all Phase 2)

- **Create PRD** (`CP` | `bmad-bmm-create-prd`) ⚡**REQUIRED** 🎭 `architect` - Expert led facilitation to produce Product Requirements Document
- **Validate PRD** (`VP` | `bmad-bmm-validate-prd`) 🎭 `architect` - Validate PRD is comprehensive, lean, well organized and cohesive
- **Create UX** (`CU` | `bmad-bmm-create-ux-design`) 🎭 `architect` - Guidance through realizing the plan for your UX
- **Validate UX** (`VU` | `bmad-bmm-create-ux-design`) 🎭 `architect` - Validates UX design deliverables

### Phase 3: Solutioning
🎭 **Agent**: `architect` (required for all Phase 3)

- **Create Architecture** (`CA` | `bmad-bmm-create-architecture`) ⚡**REQUIRED** 🎭 `architect` - Guided workflow to document technical decisions
- **Validate Architecture** (`VA` | `bmad-bmm-create-architecture`) 🎭 `architect` - Validates architecture completeness
- **Create Epics and Stories** (`CE` | `bmad-bmm-create-epics-and-stories`) ⚡**REQUIRED** 🎭 `architect` - Create the Epics and Stories listing
- **Validate Epics and Stories** (`VE` | `bmad-bmm-create-epics-and-stories`) 🎭 `architect` - Validates epics and stories completeness
- **Check Implementation Readiness** (`IR` | `bmad-bmm-check-implementation-readiness`) ⚡**REQUIRED** 🎭 `architect` - Ensure PRD, UX, Architecture and Epics/Stories are aligned

### Phase 4: Implementation
🎭 **Agent**: Switch between `scrum-master` and `dev`

- **Sprint Planning** (`SP` | `bmad-bmm-sprint-planning`) ⚡**REQUIRED** 🎭 `scrum-master` - Generate sprint plan for development tasks (kicks off implementation)
- **Sprint Status** (`SS` | `bmad-bmm-sprint-status`) 🎭 `scrum-master` - Summarize sprint status and route to next workflow
- **Create Story** (`CS` | `bmad-bmm-create-story`) ⚡**REQUIRED** 🎭 `scrum-master` - Story cycle start: Prepare first found story that is next
- **Validate Story** (`VS` | `bmad-bmm-create-story`) 🎭 `scrum-master` - Validates story readiness before development work begins
- **Dev Story** (`DS` | `bmad-bmm-dev-story`) ⚡**REQUIRED** 🎭 `dev` - Story cycle: Execute story implementation tasks and tests
- **QA Automation Test** (`QA` | `bmad-bmm-qa-automate`) 🎭 `dev` - Generate automated API and E2E tests
- **Code Review** (`CR` | `bmad-bmm-code-review`) 🎭 `dev` (recommend fresh session) - Story cycle: Review implementation quality
- **Retrospective** (`ER` | `bmad-bmm-retrospective`) 🎭 `scrum-master` - Optional at epic end: Review completed work and lessons learned

### Anytime Workflows
🎭 **Agent**: `default` (most), `tech-writer` (documentation), `dev` (quick dev)

- **Document Project** (`DP` | `bmad-bmm-document-project`) 🎭 `default` - Analyze an existing project to produce useful documentation
- **Generate Project Context** (`GPC` | `bmad-bmm-generate-project-context`) 🎭 `default` - Scan existing codebase to generate lean LLM-optimized project-context.md
- **Quick Spec** (`QS` | `bmad-bmm-quick-spec`) 🎭 `dev` - Quick one-off tasks, small changes, simple apps without extensive planning
- **Quick Dev** (`QD` | `bmad-bmm-quick-dev`) 🎭 `dev` - Quick one-off tasks, small changes, simple apps, utilities without extensive planning
- **Correct Course** (`CC` | `bmad-bmm-correct-course`) 🎭 `scrum-master` - Navigate significant changes
- **Create Dataflow** (`CDF` | `bmad-bmm-create-excalidraw-dataflow`) 🎭 `default` - Create data flow diagrams (DFD) in Excalidraw format
- **Create Diagram** (`CED` | `bmad-bmm-create-excalidraw-diagram`) 🎭 `default` - Create system architecture diagrams, ERDs, UML diagrams
- **Create Flowchart** (`CFC` | `bmad-bmm-create-excalidraw-flowchart`) 🎭 `default` - Create flowchart visualization in Excalidraw format
- **Create Wireframe** (`CEW` | `bmad-bmm-create-excalidraw-wireframe`) 🎭 `default` - Create website or app wireframes in Excalidraw format
- **Write Document** (`WD` | `bmad-bmm-write-document`) 🎭 `tech-writer` - Create technical documentation following best practices
- **Update Standards** (`US` | `bmad-bmm-update-standards`) 🎭 `tech-writer` - Update agent memory documentation-standards.md
- **Mermaid Generate** (`MG` | `bmad-bmm-mermaid-generate`) 🎭 `default` - Create a Mermaid diagram based on user description
- **Validate Document** (`VD` | `bmad-bmm-validate-document`) 🎭 `tech-writer` - Review document against documentation standards
- **Explain Concept** (`EC` | `bmad-bmm-explain-concept`) 🎭 `tech-writer` - Create clear technical explanations with examples and diagrams

---

## 🎨 CIS (Creative Innovation Strategy)
**Innovation, problem-solving and design thinking**

🎭 **Agent**: `default` (all CIS workflows)

- **Innovation Strategy** (`IS` | `bmad-cis-innovation-strategy`) - Identify disruption opportunities and architect business model innovation
- **Problem Solving** (`PS` | `bmad-cis-problem-solving`) - Apply systematic problem-solving methodologies
- **Design Thinking** (`DT` | `bmad-cis-design-thinking`) - Guide human-centered design processes using empathy-driven methodologies
- **Brainstorming** (`BS` | `bmad-cis-brainstorming`) - Facilitate brainstorming sessions using one or more techniques
- **Storytelling** (`ST` | `bmad-cis-storytelling`) - Craft compelling narratives using proven story frameworks

---

## 🧪 TEA (Test Excellence Architect)
**Testing and quality assurance**

🎭 **Agent**: `dev` (all TEA workflows)

### Phase 0: Learning
- **Teach Me Testing** (`TMT` | `bmad_tea_teach-me-testing`) 🎭 `dev` - Teach testing fundamentals through 7 sessions (TEA Academy)

### Phase 3: Solutioning
- **Test Framework** (`TF` | `bmad_tea_framework`) 🎭 `dev` - Initialize production-ready test framework
- **CI Setup** (`CI` | `bmad_tea_ci`) 🎭 `dev` - Configure CI/CD quality pipeline
- **Test Design** (`TD` | `bmad_tea_test-design`) 🎭 `dev` - Risk-based test planning

### Phase 4: Implementation
- **ATDD** (`AT` | `bmad_tea_atdd`) 🎭 `dev` - Generate failing tests (TDD red phase)
- **Test Automation** (`TA` | `bmad_tea_automate`) 🎭 `dev` - Expand test coverage
- **Test Review** (`RV` | `bmad_tea_test-review`) 🎭 `dev` - Quality audit (0-100 scoring)
- **NFR Assessment** (`NR` | `bmad_tea_nfr-assess`) 🎭 `dev` - Non-functional requirements
- **Traceability** (`TR` | `bmad_tea_trace`) 🎭 `dev` - Coverage traceability and gate

---

## 🔧 CORE (Core Utilities)
**Universal utilities and tasks**

🎭 **Agent**: `default` (all CORE workflows)

- **Brainstorming** (`BSP` | `bmad-brainstorming`) - Generate diverse ideas through interactive techniques
- **Party Mode** (`PM` | `bmad-party-mode`) - Orchestrate multi-agent discussions
- **bmad-help** (`BH` | `bmad-help`) - Get unstuck by showing what workflow steps come next
- **Index Docs** (`ID` | `bmad-index-docs`) - Create lightweight index for quick LLM scanning
- **Shard Document** (`SD` | `bmad-shard-doc`) - Split large documents into smaller files by sections
- **Editorial Review - Prose** (`EP` | `bmad-editorial-review-prose`) - Review prose for clarity, tone, and communication issues
- **Editorial Review - Structure** (`ES` | `bmad-editorial-review-structure`) - Propose cuts, reorganization, and simplification
- **Adversarial Review (General)** (`AR` | `bmad-review-adversarial-general`) - Review content critically to find issues and weaknesses

---

## 💡 Usage Tips

1. **Start with BMM Phase 1-2** for new projects (Analysis → Planning)
2. **Use Quick Dev/Quick Spec** for brownfield projects or simple additions
3. **Follow the numbered sequence** within each phase for best results
4. **Required workflows** (⚡) are critical checkpoints in the BMM flow
5. **Switch agents** (🎭) before running workflows - use `*agent <agent-name>`

### Agent Switching Examples:
```
*agent architect          # Switch to architect for planning/design
*agent scrum-master       # Switch to scrum-master for sprint management
*agent dev                # Switch to dev for implementation
*agent tech-writer        # Switch to tech-writer for documentation
*agent default            # Switch back to default mode
```

To invoke any workflow, use: `*[CODE]` or `*[COMMAND]`  
Example: `*CP` or `*bmad-bmm-create-prd`

### Typical Workflow Progression:
1. **Planning** → `*agent architect` → `*CP` (Create PRD) → `*CA` (Create Architecture) → `*CE` (Create Epics)
2. **Sprint Start** → `*agent scrum-master` → `*SP` (Sprint Planning) → `*CS` (Create Story)
3. **Development** → `*agent dev` → `*DS` (Dev Story) → `*CR` (Code Review)
4. **Next Story** → `*agent scrum-master` → `*SS` (Sprint Status) → `*CS` (Create next Story)

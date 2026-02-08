# Websoft9 Project - AI Collaboration Guidelines

## Project Context

**websoft9** is an open-source, GitOps-driven application deployment platform for single-server scenarios, designed for teams without dedicated DevOps capabilities. Combines 300+ app store with Infrastructure as Code.

**Target Users**: SMBs, indie developers, small teams (novice to intermediate skill level)

**Core Philosophy**: More powerful than basic tools, simpler than enterprise platforms

---

## Key Principles

1. **Single-Server Optimization** - No cluster/distributed architecture assumptions
2. **Technology Neutrality** - In public docs, use generic terms ("reverse proxy" not "Nginx", "Git server" not "Gitea")
3. **Simplicity First** - Avoid unnecessary complexity
4. **GitOps Native** - Infrastructure as Code through Git

---

## BMAD Method Integration

**This project uses BMAD (load on demand):**

- ✅ For **structured work** (features, planning, architecture): Use `*bmad-help` to find the right workflow
- ✅ For **quick tasks** (bugs, questions, small changes): Chat freely with these guidelines

**Common BMAD Commands:**
- `*bmad-help` - Show available workflows
- `*QD` - Quick Dev (rapid implementation)
- `*CB` - Create Product Brief
- `*CP` - Create PRD

**BMAD Configuration:**
- User: Websoft9 | Language: Chinese (workflow) / English (docs)
- Output: `specs/planning-artifacts/`, `specs/implementation-artifacts/`, `specs/`

---

## Quick Reference

**Key Documents** (detailed standards and guidelines are there):
- PRD: `specs/planning-artifacts/prd.md`
- Architecture: `specs/planning-artifacts/architecture.md`
- UI design: `specs/planning-artifacts/coding-decisions#ui.md`

**When In Doubt:**
1. Does this serve SMBs without DevOps expertise?
2. Does this add unnecessary complexity?
3. Should specific tech names be abstracted in public content?

---

**Remember**: Detailed conventions and standards are in project docs. Load them when needed. Keep this lean.

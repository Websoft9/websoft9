# Epic 6: Services Plugin - Container Process Management

## Overview

**Objective**: Create lightweight services plugin for monitoring and managing multiple processes inside containers

**Business Value**: Enable users to view, monitor, and control container services without complex CLI operations

**Priority**: P1

**Status**: Not Started

## Scope

Build minimal Cockpit plugin for container process management:
- List all processes/services running inside containers
- Display real-time service status
- Start/stop/restart operations for services

## Success Criteria

- Services list displays all running processes in containers
- Status reflects real-time state (running, stopped, failed)
- Start/stop/restart operations execute successfully
- Clean, simple UI following Cockpit design patterns
- No external dependencies beyond Cockpit APIs

## Stories

- [ ] 6.1: Service List & Status Display
- [ ] 6.2: Service Control Operations (Start/Stop/Restart)

## Dependencies

- Prerequisites: Cockpit installed, Docker/Podman containers running
- Downstream: None

## Technical Notes

- Technology: React + PatternFly (following cockpit-files patterns)
- Location: `/data/dev/websoft9/plugins/services`
- Integration: Cockpit APIs for container process management
- Keep it minimal: Focus on core functionality only

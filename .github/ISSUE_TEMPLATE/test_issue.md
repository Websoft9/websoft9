---
name: Release Test Plan
about: Validate stability and functionality of the new release
title: 'Release Test for Version 2.x.x'
labels: 'function, priority: high'
assignees: ''
---

## Test Overview
**Release Version**: 2.x.x  
**Test Environment**:  
- OS: [e.g. Ubuntu 24.04 / CentOS Stream]

## Test Content

- [ ] Verify on websoft9's menu all 4 containers are running:  
    `websoft9-apphub | websoft9-git | websoft9-proxy | websoft9-deployment`
    
- [ ] Check health status by container's log

- [ ] Check the main funtion(install a app,uninstall a app) when a fresh Installation

- [ ] Check the main funtion(install a app,uninstall a app) when upgrade websoft9

- [ ] Check the release issue content by websoft9

- [ ] Other test: anomaly testing

## Test Result

- [ ] Passed

- [ ] Failed
 - If it fails, add evidence (image or logs) to the relevant release issue
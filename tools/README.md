# Tools

This directory contains third-party tools and utilities that provide specialized functionality independent of the main Websoft9 project. These tools are standalone solutions that can be used separately or integrated into other projects.

## Available Tools

### cloudflare_downloadproxy_worker.js

A Cloudflare Worker script that implements a download proxy functionality. This script can be deployed to Cloudflare Workers to create a proxy service for downloading files.

**Usage:**
1. Deploy this script to Cloudflare Workers
2. Access the worker with a URL parameter: `https://proxy.websoft9.com/?url=https://example.com/file.zip`
3. The worker will proxy the download and set appropriate headers for file downloads

**Parameters:**
- `url` (required): The URL of the file to download through the proxy

## Purpose

These tools are designed to solve specific technical challenges and can be used independently of the main Websoft9 project. They serve as utility scripts, proxies, converters, or other specialized functions that might be useful across different projects and environments.
# Epic5 Store Plugin

A Cockpit plugin for displaying and categorizing media data in an organized manner.

## Overview

Epic5 Store is a standalone Cockpit plugin that presents media resources (logos, screenshots, data) in a categorized, user-friendly interface. It is decoupled from apphub to provide focused functionality for media management and display.

## Features

- Display media data from the media repository
- Categorized views for different types of media
- Responsive UI built with React and Material-UI
- Standalone plugin architecture

## Development

### Prerequisites

- Node.js 14+
- npm or yarn

### Installation

```bash
npm install
```

### Development Mode

```bash
npm start
```

### Build

```bash
npm run build
```

## Structure

```
epic5-store/
├── public/          # Static files and Cockpit manifest
├── src/
│   ├── components/  # React components
│   ├── pages/       # Page components
│   ├── utils/       # Utility functions
│   └── App.js       # Main application
├── epic5-store.json # Plugin metadata
└── package.json     # Dependencies
```

## License

GPL v2 or later

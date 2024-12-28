<!--
SPDX-FileCopyrightText: © 2023 Tim Weber
SPDX-FileCopyrightText: © 2023 Tobias Mühlberger

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# DearMEP Client

This project contains the client implementation of DearMEP. The client is built as a **Web Component** using **Angular Elements**.

This implementation supports general use cases for DearMEP and provides a degree of configurability, allowing for the customization of certain visual elements. For specialized use cases, you can always develop a custom implementation tailored to specific requirements.

## Features

- Multi-language support
- Stores user preferences in local storage
- Configurable and themeable
- Styles are isolated from the host page using the Shadow DOM

## Embedding DearMEP

The **DearMEP** client component can be embedded into any HTML page using the following code snippet:

```html
<link rel="stylesheet" href="https://example.org/static/dear-mep.css" />
<dear-mep host="https://example.org/"></dear-mep>
<script src="https://example.org/static/dear-mep.js" async></script>
```

Replace `https://example.org/` with the URL to your DearMEP instance, i.e. where the [server](../server/README.md) is running.

### Important Notes
- Ensure that the page’s URL is allowed in the **CORS configuration** of the DearMEP server for successful embedding (via `api.cors.origins`, see [example-config.yaml](../server/dearmep/example-config.yaml)).
- If the embedding page uses **Content Security Policy (CSP)** headers, make sure that the DearMEP script is not blocked.

If DearMEP does not appear on the page, check the browser console and developer tools for errors.

Alternatively to embedding, the client can also run as a **standalone page**, where the backend provides a simple HTML page containing the client snippet. See [Serving Static Files](../server/README.md#serving-static-files-eg-the-client) for details.

## Configuration Options

There are multiple ways to configure the client:

### 1. HTML Attributes

Attributes can be set directly on the `<dear-mep>` element to control various behaviors:

| Attribute               | Description                                                                                                                                                                                   |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `host`                  | **(Required)** The URL of the DearMEP server. Only absolute URLs are allowed.                                                                                                                 |
| `api`                   | The URL of the API server, if it is hosted separately from the main DearMEP server. Relative URLs are interpreted in relation to `host`.                                                      |
| `assets`                | The URL of the assets server if static assets are hosted separately from the API server. Relative URLs are interpreted in relation to `host`.                                                |
| `default-country`       | Fallback country if the user's location cannot be determined (e.g., due to VPN/TOR). Uses ISO 639-1 Alpha-2 codes (e.g., "DE" for Germany).                                                   |
| `disable-calling`       | Hides the calling functionality if present.                                                                                                                                                   |
| `disable-scheduling`    | Hides the schedule-call functionality if present.                                                                                                                                             |

**Example:**
```html
<dear-mep host="https://example.org/" default-country="DE"></dear-mep>
```

For a detailed technical description, refer to the source code in [app.component.ts](../client/src/app/app.component.ts).

### 2. Server Configuration

On startup, the client loads configurations from the server, including enabled features and localization strings. These configurations are set in the server’s config file (see: [example-config.yaml](../server/dearmep/example-config.yaml)).

### 3. Build-Time Configuration

Certain aspects of the client can be configured at build-time, allowing different settings for environments such as *development* or *production*. This is managed in [environment.ts](./src/environments/environment.ts).

## Styling and Theming

The styles for the client are built using **SCSS** and are split into two stylesheets: `dear-mep.css` and `dear-mep-inner.css`.

- `dear-mep.css` is loaded into the host page using a `<link>` tag and applies styles outside of the shadow root.
- `dear-mep-inner.css` is loaded within the Shadow DOM, ensuring that these styles are isolated from the host page.

### Theming

For details on customizing the appearance of the DearMEP client, refer to the [theming documentation](../doc/theming.md).

## Development Instructions

### Installing Dependencies

To set up the project for local development, run:

```bash
npm install
```

### Generating the API Client

Before building the frontend, it is required generate the API client code. This step ensures that the frontend is able to communicate with the backend API.

> **Note:** Regenerate the client whenever there are API changes to avoid build errors.

**Using the Latest OpenAPI Specification**

The easiest way to generate the API client is by running the following command. This will use the latest OpenAPI specification based on the `main` branch, available [hrer](https://akvorrat.github.io/dearmep/openapi.json).

    npm run generate-client:remote

**Using a Locally Running Server**

In case the server is running locally, it is possible to generate the API client with the following command. This method is recommended because it guarantees that the generated client matches the API version of the local server:

    npm run generate-client:local

**Using a Custom OpenAPI Specification**

Alternatively, it is possible to generate the API client using a custom OpenAPI specification. Save the specification file as `openapi.json` in the root directory of the repository. For guidance on generating this file, refer to [Retrieving the OpenAPI specification](../server/README.md#retrieving-the-openapi-specification).

    npm run generate-client

### Running the Development Server

To start the development server:

```bash
npm start
```

Navigate to [http://localhost:4200](http://localhost:4200/). The application will automatically reload if you make changes to the source files.

### Serving the Embedding Test Page

To test the embedded client:

1. Build the project:

   ```bash
   npm run build
   ```

2. Start the test server:

   ```bash
   npm run start:test-page
   ```

3. Access the test page at [http://localhost:8080](http://localhost:8080).

## Analyzing Bundle Size

To analyze the bundle size:

1. Build the application:

   ```bash
   npm run build
   ```

2. Use the [esbuild Bundle Size Analyzer](https://esbuild.github.io/analyze/) and upload `dist/dear-mep/stats.json`.

## Code Scaffolding

To generate a new component:

```bash
npx ng generate component component-name
```

Other entities can also be generated using:

```bash
ng generate directive|pipe|service|class|guard|interface|enum|module
```

## Building the Project

To build the project:

```bash
npm run build
```

The build artifacts will be stored in `dist/dear-mep-bundle/`.

## Formatting & Linting

- **Format the code** using [Prettier](https://prettier.io/):

  ```bash
  npm run format
  ```

- **Lint the code** and automatically fix issues:

  ```bash
  npm run lint
  npm run lint:fix
  ```

> **VSCode Users**: If you’re using VSCode, install the [Prettier extension](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode) and enable `"editor.formatOnSave": true` in your settings for auto-formatting.

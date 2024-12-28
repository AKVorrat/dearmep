<!--
SPDX-FileCopyrightText: © 2024 Tobias Mühlberger

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Theming the Client

The appearance of the DearMEP client can be customized using CSS, allowing you to adjust its look and feel to better fit your needs.

## CSS Custom Properties

The simplest way to customize the DearMEP client is by modifying its predefined CSS custom properties (variables). This approach lets you adjust visual aspects such as colors, fonts, and spacing without the need to recompile SCSS files.

### Where to Find Variables

The available CSS custom properties are defined in [`variables.scss`](../client/src/style/themes/variables.scss). You can also explore properties prefixed with `--dmep-` using your browser’s developer tools.

### Example Usage

Here’s an example of how to customize the client’s appearance by setting custom properties:

```css
dear-mep {
  --dmep-bg: rgba(0, 0, 0, 75%);
  --dmep-primary-color: rgb(250, 128, 114);
  /* Add more customizations as needed */
}
```

> **Note:** `--dmep-primary-color` does not affect the styles of Angular Material components.

### How It Works

To apply your custom styles, you can load an additional stylesheet with updated CSS variables or use inline styles when embedding the client. Because CSS Custom Properties can traverse the Shadow DOM, you can override values from the Light DOM. However, this method has limitations:
- Only predefined properties can be adjusted.
- Modifying other style aspects is not supported through this method.

This approach allows you to adjust styles without modifying or recompiling the client’s original stylesheets. However, it cannot be used to customize Angular Material components.

## Advanced Customization

For more extensive customizations, the above method may not suffice, particularly for styling Angular Material components. In such cases, you can create custom stylesheets by modifying the files in `/client/src/style/`. These stylesheets are compiled into CSS as part of the client’s build process.

> **Caution:** When [overriding arbitrary styles](#overriding-arbitrary-styles), be mindful of potential breaking changes in future releases.

> **Note:** We acknowledge that theming the client can be complex and are working to simplify it in future releases.

### Stylesheets

The client’s styles are compiled into two main stylesheets:
- **`dear-mep.css`** – Loaded in the Light DOM.
- **`dear-mep-inner.css`** – Loaded in the Shadow DOM.

Most styling changes must be applied in the Shadow DOM. However, certain assets like fonts need to be loaded in the Light DOM to be usable within the Shadow DOM.

You can include multiple versions of the stylesheets in a single instance. The `assets` [attribute](../client/README.md#1-html-attributes) specifies where to find static assets, including stylesheets.

### Angular Material 2 Components

The DearMEP client uses **Angular Material 2** components, which support customization through theming. For advanced control over the appearance, you can create a custom theme following the [Angular Material Theming Guide](https://material.angular.io/guide/material-2-theming).

The client’s current theme is defined in [`default-dark.scss`](../client/src/style/themes/default-dark.scss). At present, only a dark theme is provided, though more themes may be added in future releases.

## Overriding Arbitrary Styles

If adjusting custom properties and Angular Material themes does not meet your needs, you can override specific styles in `dear-mep-inner.css`. Use this method cautiously, as it can introduce instability.

### Considerations for Overriding Styles

- **Stability**: There is no guarantee that internal selectors will remain consistent across future releases of the DearMEP client or its underlying component library.
- **Responsiveness**: Overriding styles can affect the client’s responsive behavior, potentially causing issues on different screen sizes and languages.

> **Recommendation**: When overriding styles, aim to modify as few elements as possible. Thoroughly test your changes across various screen sizes and languages to ensure compatibility.

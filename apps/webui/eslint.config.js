import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      'react-hooks/incompatible-library': 'off',
    },
  },
  {
    files: ['src/**/*.{tsx,jsx}'],
    ignores: ['src/components/ui/**', 'src/test/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXOpeningElement[name.name='button']",
          message: 'Use shared Button from "@/components/ui/button" in page/feature layers; keep raw <button> only in ui primitives.',
        },
      ],
    },
  },
  {
    files: ['src/components/ui/**/*.{ts,tsx,js,jsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])

-- https://astronvim.github.io/
-- :AstroUpdate

local config = {
  lsp = {
    servers = {
      "angularls",
      "eslint"
    },
  },

  plugins = {
    treesitter = {
      -- ensure_installed = { "fish", "lua", "typescript" },
    },
  }
}

return config

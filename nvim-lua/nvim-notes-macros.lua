-- Add this to your init.lua
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.md",
  callback = function()
    local datetime = os.date("%Y-%m-%d %H:%M:%S")
    local buf = 0

    -- How many lines to scan (up to 5, or total lines if fewer)
    local line_count = vim.api.nvim_buf_line_count(buf)
    local end_line   = math.min(5, line_count)

    -- Grab those lines
    local lines = vim.api.nvim_buf_get_lines(buf, 0, end_line, false)

    local found = false
    for i, line in ipairs(lines) do
      if line:match("last updated:") then
        -- Replace everything after "last updated:" with the new datetime
        lines[i] = line:gsub("last updated:%s*.*", "last updated: " .. datetime)
        found = true
        break
      end
    end

    -- Write back the possibly‑updated block
    vim.api.nvim_buf_set_lines(buf, 0, end_line, false, lines)

    -- If we never saw a "last updated:" in those first lines, insert one at the top
    if not found then
      vim.api.nvim_buf_set_lines(buf, 0, 0, false, {
        "last updated: " .. datetime
      })
    end
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    local function open_markdown_url_under_cursor()
      local line = vim.api.nvim_get_current_line()
      local col = vim.fn.col(".")
      local before = line:sub(1, col)
      local after = line:sub(col)

      -- try to match a markdown link in the full line
      local full_link = line:match("%[.-%]%((.-)%)")
      if full_link and full_link:match("^https?://") then
        vim.fn.jobstart({ "open", full_link }, { detach = true })
        return
      end

      -- fallback: try getting word under cursor
      local word = vim.fn.expand("<cfile>")
      if word:match("^https?://") then
        vim.fn.jobstart({ "open", word }, { detach = true })
      else
        vim.cmd("edit " .. word)
      end
    end

    vim.keymap.set("n", "gf", open_markdown_url_under_cursor, { buffer = true })
    vim.keymap.set("n", "gd", open_markdown_url_under_cursor, { buffer = true })
  end,
})


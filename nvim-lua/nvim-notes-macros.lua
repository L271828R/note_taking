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


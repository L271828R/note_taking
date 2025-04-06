-- Add this to your init.lua configuration file
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.md",
  callback = function()
    local datetime = os.date("%Y-%m-%d %H:%M:%S")
    -- Get the first five lines or the total number of lines if fewer than 5
    local line_count = vim.api.nvim_buf_line_count(0)
    local end_line = math.min(5, line_count)
    local lines = vim.api.nvim_buf_get_lines(0, 0, end_line, false)
    for i, line in ipairs(lines) do
      if line:match("last updated:") then
        -- Replace text after "last updated:" with the new datetime
        lines[i] = line:gsub("last updated:%s*.*", "last updated: " .. datetime)
      end
    end
    vim.api.nvim_buf_set_lines(0, 0, end_line, false, lines)
  end,
})


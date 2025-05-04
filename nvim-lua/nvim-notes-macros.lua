-- ~/projects/notes/nvim-lua/nvim-notes-macros.lua

-- 1. Paths
local vault_dir = vim.fn.expand(vim.fn.getenv("NOTES_PATH")         or "~/projects/notes")
local notes_dir = vim.fn.expand(vim.fn.getenv("NOTES_FOLDERS_PATH") or vault_dir .. "/folders")
local map_path  = vault_dir  .. "/.note_map.json"
local log_path  = vault_dir  .. "/.note_map.log"

-- 2. Logger
local function write_log(msg)
  local f = io.open(log_path, "a")
  if f then
    f:write(os.date("%Y-%m-%d %H:%M:%S") .. "  " .. msg .. "\n")
    f:close()
  end
end

write_log("=== Plugin load start ===")
write_log("Vault dir: " .. vault_dir)
write_log("Notes dir: " .. notes_dir)
write_log("Map file: " .. map_path)

-- 3. JSON helpers
local has_cjson, cjson = pcall(require, "cjson.safe")
local json_decode = has_cjson and cjson.decode or vim.fn.json_decode
local json_encode = has_cjson and cjson.encode or vim.fn.json_encode

-- 4. fzf-lua client
local fzf = require("fzf-lua")

-- 5. Module table
local M = {}

-- 6. Ensure map exists
do
  write_log("INIT: checking map file")
  local f = io.open(map_path, "r")
  if not f then
    write_log("INIT: creating empty map")
    local nf = io.open(map_path, "w")
    nf:write("{}")
    nf:close()
  else
    f:close()
    write_log("INIT: map exists")
  end
end

-- 7. load_map and save_map functions
local function load_map()
  write_log("load_map: opening " .. map_path)
  local f = io.open(map_path, "r")
  if not f then return {} end
  local data = f:read("*a"); f:close()
  write_log("load_map: raw JSON: " .. data:gsub("\n","\\n"))
  local ok, tbl = pcall(json_decode, data)
  if not ok then
    write_log("load_map: JSON decode error")
    return {}
  end
  write_log("load_map: entries=" .. vim.tbl_count(tbl))
  return tbl
end

local function save_map(m)
  write_log("save_map: encoding map")
  local ok, out = pcall(json_encode, m)
  if not ok then
    write_log("save_map: encode error: " .. tostring(out))
    return
  end

  if vim.fn.executable("python3") == 1 then
    write_log("save_map: pretty-printing JSON")
    local pretty = vim.fn.system({"python3","-m","json.tool"}, out)
    if vim.v.shell_error == 0 then
      out = pretty
    else
      write_log("save_map: pretty-print failed, using compact JSON")
    end
  end

  write_log("save_map: writing JSON to " .. map_path)
  local f = io.open(map_path, "w")
  if not f then
    write_log("save_map: cannot open map for write")
    return
  end
  f:write(out)
  f:close()
end

-- 8. update_map_file: inject path and title into the JSON map
local function update_map_file(path)
  write_log("update_map_file: " .. path)
  local f = io.open(path, "r")
  if not f then return write_log("  cannot open MD file") end
  local content = f:read("*a"); f:close()

  -- Updated pattern to match ID with flexible spacing
  local id = content:match("<!%-%- id:%s*([0-9a-f]+)%s*%-%->")
  if not id then 
    -- Try alternative format as fallback
    id = content:match("<!-- id: ([0-9a-f]+) -->")
  end
  
  if not id then 
    write_log("  no id found using any pattern, skipping")
    return 
  end

  write_log("  found ID: " .. id)
  local rel = path:sub(#vault_dir + 2)
  local title = content:match("#%s*Title:%s*(.-)\r?\n")
              or content:match("#%s*(.-)\r?\n")
              or rel:match("([^/]+)%.md$")

  local map = load_map()
  map[id] = { path = rel, title = title }
  save_map(map)
end

-- 9. ensure_id: add an 8-hex ID comment if missing, then update map
local function ensure_id(path)
  write_log("ensure_id: " .. path)
  local f = io.open(path, "r")
  if not f then return end
  local content = f:read("*a"); f:close()

  -- Updated pattern to match ID with flexible spacing
  local id = content:match("<!%-%- id:%s*([0-9a-f]+)%s*%-%->")
  if not id then 
    -- Try alternative format as fallback
    id = content:match("<!-- id: ([0-9a-f]+) -->")
  end
  
  if not id then
    id = string.format("%08x", math.random(0,0xFFFFFFFF))
    write_log("injecting new id: " .. id)
    local w = io.open(path, "w")
    w:write("<!-- id: " .. id .. " -->\n" .. content)
    w:close()
  end
  update_map_file(path)
  return id
end

-- 10. insert_link: fuzzy search filenames, contents, or titles
function M.insert_link()
  write_log("insert_link: start")
  local mode = vim.fn.input("Search mode (c)ontent/(f)ilenames/(t)itles [c]: ")

  if mode:sub(1,1) == "f" then
    -- Filename mode
    fzf.files({
      cwd        = notes_dir,
      prompt     = "Search filenames ▶︎ ",
      file_icons = false,
      actions = {
        ["default"] = function(sel)
          local rel  = sel[1]:gsub("^%s+", "")
          local full = notes_dir .. "/" .. rel
          local id   = ensure_id(full)
          if not id then return end
          local map   = load_map()
          local title = map[id] and map[id].title or ""
          local link  = title ~= "" and string.format("[[%s|%s]]", id, title)
                              or string.format("[[%s]]", id)
          vim.api.nvim_put({ link }, "c", true, true)
        end,
      },
    })

  elseif mode:sub(1,1) == "t" then
    -- Title mode
    local map = load_map()
    local items = {}
    for id, info in pairs(map) do
      table.insert(items, string.format("%s  %s", id, info.title))
    end
    table.sort(items)
    fzf.fzf_exec(function(cb)
      for _, line in ipairs(items) do cb(line) end
      cb()
    end, {
      prompt = "Search titles ▶︎ ",
      actions = {
        ["default"] = function(sel)
          local pick = sel[1]:match("^([0-9a-f]+)")
          if not pick then return end
          local info = map[pick]
          ensure_id(vault_dir .. "/" .. info.path)
          local link = string.format("[[%s|%s]]", pick, info.title)
          vim.api.nvim_put({ link }, "c", true, true)
        end,
      },
    })

  else
    -- Content mode (default)
    fzf.grep({
      cwd        = notes_dir,
      prompt     = "Search content ▶︎ ",
      rg_opts    = "--column --line-number --no-heading --color=never --smart-case -e",
      file_icons = false,
      actions = {
        ["default"] = function(sel)
          local rel  = sel[1]:gsub("^%s+", ""):match("^([^:]+):")
          local full = notes_dir .. "/" .. rel
          local id   = ensure_id(full)
          if not id then return end
          local map   = load_map()
          local title = map[id] and map[id].title or ""
          local link  = title ~= "" and string.format("[[%s|%s]]", id, title)
                              or string.format("[[%s]]", id)
          vim.api.nvim_put({ link }, "c", true, true)
        end,
      },
    })
  end
end

-- 11. insert_ids: batch add missing IDs across all notes
function M.insert_ids()
  write_log("insert_ids: start")
  for file in io.popen('find "'..notes_dir..'" -type f -name "*.md"'):lines() do
    ensure_id(file)
  end
  vim.notify("✅ insert_ids() completed")
end

-- 12. goto_note: jump to outgoing [[id]] link(s)
function M.goto_note()
  write_log("goto_note: start")
  local head = vim.api.nvim_buf_get_lines(0, 0, 5, false)
  local cur_id
  for _, l in ipairs(head) do
    -- Updated pattern to match ID with flexible spacing
    cur_id = l:match("<!%-%- id:%s*([0-9a-f]+)%s*%-%->")
    if not cur_id then 
      -- Try alternative format as fallback
      cur_id = l:match("<!-- id: ([0-9a-f]+) -->")
    end
    if cur_id then break end
  end
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local ids = {}
  for _, ln in ipairs(lines) do
    for id in ln:gmatch("%[%[([0-9a-f]+)[^%]]*%]%]") do
      if id ~= cur_id then ids[id] = true end
    end
  end
  local map = load_map()
  local targets = {}
  for id in pairs(ids) do
    if map[id] then table.insert(targets, { id = id, path = map[id].path, title = map[id].title }) end
  end
  if #targets == 0 then
    vim.notify("No outgoing links", vim.log.levels.INFO)
    return
  elseif #targets == 1 then
    vim.cmd("edit " .. vim.fn.fnameescape(vault_dir .. "/" .. targets[1].path))
    return
  end
  local items = {}
  for _, t in ipairs(targets) do
    table.insert(items, string.format("%s  %s", t.id, t.title))
  end
  table.sort(items)
  fzf.fzf_exec(function(cb)
    for _, it in ipairs(items) do cb(it) end
    cb()
  end, {
    prompt = "Linked notes ▶︎ ",
    actions = {
      ["default"] = function(sel)
        local pick = sel[1]:match("^([0-9a-f]+)")
        local p = map[pick]
        vim.cmd("edit " .. vim.fn.fnameescape(vault_dir .. "/" .. p.path))
      end,
    },
  })
end

-- NEW FUNCTION: ensure a single ID at the top of the file
local function ensure_single_id(buf)
  local filepath = vim.api.nvim_buf_get_name(buf)
  if not filepath:match("%.md$") or filepath:sub(1, #vault_dir) ~= vault_dir then
    return
  end
  
  write_log("ensure_single_id: checking " .. filepath)
  
  -- Get the whole file content
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  
  -- Log the regex pattern we're using
  local regex_pattern = "<!%-%- id:%s*([0-9a-f]+)%s*%-%->$"
  write_log("Using regex pattern: " .. regex_pattern)
  
  -- Collect all ID lines and their positions
  local id_lines = {}
  local has_id = false
  local id_value = nil
  
  write_log("Scanning " .. #lines .. " lines for ID comments:")
  for i, line in ipairs(lines) do
    -- Try the standard pattern first
    local id = line:match("<!-- id: ([0-9a-f]+) -->")
    if id then
      write_log("  ✓ MATCH FOUND (standard format): id=" .. id)
      table.insert(id_lines, {index = i, line = line, id = id})
      has_id = true
      if not id_value then
        id_value = id
      end
    else
      -- Try the relaxed pattern as fallback
      id = line:match("<!%-%- id:%s*([0-9a-f]+)%s*%-%->")
      if id then
        write_log("  ✓ MATCH FOUND (relaxed format): id=" .. id)
        table.insert(id_lines, {index = i, line = line, id = id})
        has_id = true
        if not id_value then
          id_value = id
        end
      else
        write_log("  ✗ NO MATCH on line: " .. line:sub(1, 40))
      end
    end
  end
  
  write_log("ID scan complete. Found " .. #id_lines .. " ID lines.")
  
  -- What should we do with the file?
  if #id_lines == 0 then
    -- No ID: Add one at the top
    local id = string.format("%08x", math.random(0,0xFFFFFFFF))
    write_log("No IDs found. Adding new ID " .. id .. " to " .. filepath)
    
    -- Insert at top with a blank line after it
    vim.api.nvim_buf_set_lines(0, 0, 0, false, {
      "<!-- id: " .. id .. " -->", 
      "" -- Empty line after ID
    })
    
    id_value = id
    
  elseif #id_lines > 1 then
    -- Multiple IDs: Keep only the first one
    write_log("Multiple IDs found. Keeping only first ID: " .. id_value)
    
    write_log("Lines to be removed:")
    for j, id_info in ipairs(id_lines) do
      if j > 1 then
        write_log(string.format("  Line %d: '%s'", id_info.index, id_info.line))
      end
    end
    
    -- Create new lines array without the duplicate IDs
    local new_lines = {}
    for i, line in ipairs(lines) do
      local skip_line = false
      
      for j, id_info in ipairs(id_lines) do
        if j > 1 and i == id_info.index then
          skip_line = true
          break
        end
      end
      
      if not skip_line then
        table.insert(new_lines, line)
      end
    end
    
    write_log("Replacing buffer content with " .. #new_lines .. " lines (removed " .. 
              (#lines - #new_lines) .. " duplicate ID lines)")
    
    -- Replace the buffer content
    vim.api.nvim_buf_set_lines(0, 0, -1, false, new_lines)
  else
    write_log("Single ID found: " .. id_value .. ". No changes needed to ID.")
  end
  
  -- Return the ID for map updating
  return id_value
end

-- 13. Autocmds & keymaps for Markdown workflows
-- Create a single augroup for all our Markdown-related autocmds
local markdown_group = vim.api.nvim_create_augroup("MarkdownSetup", { clear = true })

-- Position cursor at top of file when opening Markdown files
vim.api.nvim_create_autocmd({"BufEnter", "BufWinEnter", "BufReadPost"}, {
  pattern = "*.md",
  callback = function()
    -- Use direct API call to position cursor at line 1
    vim.defer_fn(function()
      vim.api.nvim_win_set_cursor(0, {1, 0})
      write_log("Cursor positioned at top of file")
    end, 10) -- Small delay to let other processes finish
  end,
  group = markdown_group
})

-- Ensure ID exists and is unique
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.md",
  callback = function(args)
    local id = ensure_single_id(args.buf)
    if id then
      write_log("BufWritePre: ID management complete, id=" .. id)
    end
  end,
  group = markdown_group
})

-- Update map file after saving
vim.api.nvim_create_autocmd("BufWritePost", {
  pattern = "*.md",
  callback = function(args)
    local f = vim.api.nvim_buf_get_name(args.buf)
    if f:sub(1, #vault_dir) == vault_dir then
      update_map_file(f)
    end
  end,
  group = markdown_group
})

-- Setup URL handling for Markdown files
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    local function open_url()
      local url = vim.fn.expand("<cfile>")
      if url:match("^https?://") then
        vim.fn.jobstart({ "open", url }, { detach = true })
      else
        vim.cmd("edit " .. url)
      end
    end
    vim.keymap.set("n", "gf", open_url, { buffer = true })
    vim.keymap.set("n", "gd", open_url, { buffer = true })
  end,
  group = markdown_group
})

-- 14. Keymaps
vim.keymap.set("n", "<leader>ln", M.insert_link, { desc = "Insert note link via fzf" })
vim.keymap.set("n", "<leader>gf", M.goto_note,   { desc = "Go to outgoing note link" })

write_log("=== Plugin load end ===")

-- Function to enforce 80 character line length in markdown files
function EnforceMarkdownLineLength()
  -- Save cursor position
  local cursor_pos = vim.fn.getcurpos()
  
  -- Get all lines in the current buffer
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local new_lines = {}
  
  for _, line in ipairs(lines) do
    -- Skip lines that are already under 80 characters
    if #line <= 80 then
      table.insert(new_lines, line)
    else
      -- Process lines longer than 80 characters
      local current_line = line
      
      while #current_line > 80 do
        -- Find the last space before the 80th character
        local break_point = 0
        for i = 80, 1, -1 do
          if current_line:sub(i, i) == " " then
            break_point = i
            break
          end
        end
        
        -- If no space found, break at character 80
        if break_point == 0 then
          break_point = 80
        end
        
        -- Insert the line segment before the break point
        table.insert(new_lines, current_line:sub(1, break_point))
        
        -- Continue with the rest of the line
        current_line = current_line:sub(break_point + 1)
      end
      
      -- Add remaining part of the line if any
      if #current_line > 0 then
        table.insert(new_lines, current_line)
      end
    end
  end
  
  -- Replace buffer contents with new lines
  vim.api.nvim_buf_set_lines(0, 0, -1, false, new_lines)
  
  -- Restore cursor position
  vim.fn.setpos('.', cursor_pos)
end

-- Create a command that can be called manually
vim.api.nvim_create_user_command('EnforceMarkdownLineLength', function()
  EnforceMarkdownLineLength()
end, {})


return M

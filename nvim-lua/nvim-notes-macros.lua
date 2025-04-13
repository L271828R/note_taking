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

-- 4. fzf‑lua
local fzf = require("fzf-lua")

-- 5. Ensure map exists
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

-- 6. load_map / save_map
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
  local cnt = 0; for _ in pairs(tbl) do cnt = cnt + 1 end
  write_log("load_map: entries="..cnt)
  return tbl
end

-- 6. save_map: encode, pretty‑print, then log final contents
local function save_map(m)
  write_log("save_map: encoding map")
  local ok, out = pcall(json_encode, m)
  if not ok then
    write_log("save_map: encode error: " .. tostring(out))
    return
  end

  -- pretty‑print via python3 if available
  if vim.fn.executable("python3") == 1 then
    write_log("save_map: pretty‑printing JSON with python3 json.tool")
    local pretty = vim.fn.system({ "python3", "-m", "json.tool" }, out)
    if vim.v.shell_error == 0 then
      out = pretty
    else
      write_log("save_map: json.tool failed, falling back to compact")
    end
  else
    write_log("save_map: python3 not found, writing compact JSON")
  end

  write_log("save_map: writing JSON to " .. map_path)
  local f = io.open(map_path, "w")
  if not f then
    write_log("save_map: cannot open for write")
    return
  end
  f:write(out)
  f:close()

  -- re‑read and log what actually landed on disk
  local f2 = io.open(map_path, "r")
  if f2 then
    local final = f2:read("*a"); f2:close()
    write_log("save_map: final map contents (truncated): "
      .. final:sub(1,200):gsub("\n","\\n")
      .. (#final>200 and "…" or ""))
  else
    write_log("save_map: failed to re‑open map for logging")
  end
end



-- 7. update_map_file (literal <!-- id: abc12345 -->, rel w.r.t. vault_dir)
local function update_map_file(path)
  write_log("update_map_file: " .. path)
  local f = io.open(path, "r")
  if not f then
    write_log("  cannot open MD file")
    return
  end
  local content = f:read("*a"); f:close()
  write_log("  MD raw (truncated): " .. content:sub(1,200):gsub("\n","\\n") .. (#content>200 and "…" or ""))

  -- escaped hyphens to match your injected ID
  local id = content:match("<!%-%- id: ([0-9a-f]+) %-%->")
  write_log("  parsed id: " .. tostring(id))
  if not id then
    write_log("  no id, skipping map update")
    return
  end

  -- relative to vault_dir
  local rel = path:sub(#vault_dir + 2)
  write_log("  rel path: " .. rel)

  local title = content:match("#%s*Title:%s*(.-)\r?\n")
             or content:match("#%s*(.-)\r?\n")
             or rel:match("([^/]+)%.md$")
  write_log("  parsed title: " .. tostring(title))

  local m = load_map()
  m[id] = { path = rel, title = title }
  save_map(m)
end

-- 8. ensure_id (scan full file, inject if missing, then update)
local function ensure_id(path)
  write_log("ensure_id: " .. path)
  local f = io.open(path, "r")
  if not f then
    write_log("  cannot open MD file")
    return nil
  end
  local content = f:read("*a"); f:close()

  local id = content:match("<!%-%- id: ([0-9a-f]+) %-%->")
  if id then
    write_log("  found existing id: " .. id)
  else
    id = string.format("%08x", math.random(0,0xFFFFFFFF))
    write_log("  injecting new id: " .. id)
    local wf = io.open(path, "w")
    wf:write("<!-- id: " .. id .. " -->\n" .. content)
    wf:close()
  end

  update_map_file(path)
  return id
end

-- 9. autocmd: on save, update map only
-- 9. autocmd: on save, update map only for files in your vault
-- 9. autocmd: on save, update map only for files under your vault
-- 9. autocmd: on save, update map only for files under your vault
-- 9. autocmd: on save, update map only for vault files (with logging)
vim.api.nvim_create_autocmd("BufWritePost", {
  pattern = "*.md",
  callback = function(args)
    -- use the full path from the buffer, not args.file
    local file = vim.api.nvim_buf_get_name(args.buf)
    write_log("BufWritePost fired for: " .. file)

    if file:sub(1, #vault_dir) ~= vault_dir then
      write_log("  skipping: not under vault_dir")
      return
    end

    write_log("  calling update_map_file for: " .. file)
    update_map_file(file)
  end,
})


-- 10. last‑updated stamp (unchanged)
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.md",
  callback = function()
    local dt = os.date("%Y-%m-%d %H:%M:%S")
    local buf = 0
    local lines = vim.api.nvim_buf_get_lines(buf, 0, math.min(5, vim.api.nvim_buf_line_count(buf)), false)
    local found = false
    for i, l in ipairs(lines) do
      if l:match("last updated:") then
        lines[i] = "last updated: " .. dt
        found = true
        break
      end
    end
    if found then
      vim.api.nvim_buf_set_lines(buf, 0, #lines, false, lines)
    else
      vim.api.nvim_buf_set_lines(buf, 0, 0, false, { "last updated: " .. dt })
    end
  end,
})

-- 11. URL opener (unchanged)
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    local function open_url()
      local line = vim.api.nvim_get_current_line()
      local url  = line:match("%[.-%]%((.-)%)") or vim.fn.expand("<cfile>")
      if url:match("^https?://") then
        vim.fn.jobstart({ "open", url }, { detach = true })
      else
        vim.cmd("edit " .. url)
      end
    end
    vim.keymap.set("n", "gf", open_url, { buffer = true })
    vim.keymap.set("n", "gd", open_url, { buffer = true })
  end,
})

-- 12. Exports: insert_link, insert_ids
local M = {}

function M.insert_link()
  write_log("insert_link: start")
  local mode = vim.fn.input("Search mode (c)ontent/(f)ilenames [c]: ")
  if mode:sub(1,1) == "f" then
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
          local m     = load_map()
          local title = m[id] and m[id].title or ""
          local link  = title ~= "" and string.format("[[%s|%s]]", id, title)
                                or string.format("[[%s]]", id)
          vim.api.nvim_put({ link }, "c", true, true)
        end,
      },
    })
  else
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
          local m     = load_map()
          local title = m[id] and m[id].title or ""
          local link  = title ~= "" and string.format("[[%s|%s]]", id, title)
                                or string.format("[[%s]]", id)
          vim.api.nvim_put({ link }, "c", true, true)
        end,
      },
    })
  end
end

function M.insert_ids()
  write_log("insert_ids: start")
  for file in io.popen('find "' .. notes_dir .. '" -type f -name "*.md"'):lines() do
    local f = io.open(file, "r")
    if not f then goto cont end
    local content = f:read("*a"); f:close()
    if not content:match("<!%-%- id: [0-9a-f]+ %-%->") then
      local id = string.format("%08x", math.random(0,0xFFFFFFFF))
      write_log("insert_ids: injecting " .. id .. " into " .. file)
      local wf = io.open(file, "w")
      wf:write("<!-- id: " .. id .. " -->\n" .. content)
      wf:close()
    else
      write_log("insert_ids: skipping (has ID) " .. file)
    end
    update_map_file(file)
    ::cont::
  end
  vim.notify("✅ insert_ids() completed")
end

-- 13. Go‑to‑linked‑note: only direct [[id]]s in this buffer
function M.goto_note()
  write_log("goto_note: start")

  -- 1) this buffer’s own ID
  local head = vim.api.nvim_buf_get_lines(0, 0, 5, false)
  local cur_id
  for _, l in ipairs(head) do
    cur_id = l:match("<!%-%- id: ([0-9a-f]+) %-%->")
    if cur_id then break end
  end
  write_log("goto_note: this note’s id = " .. tostring(cur_id))

  -- 2) collect direct links (matches [[id]] and [[id|Title…]])
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local linked = {}
  for _, ln in ipairs(lines) do
    -- capture the hex ID, even if there's a |Title afterwards
    for id in ln:gmatch("%[%[([0-9a-f]+)[^%]]*%]%]") do
      if id ~= cur_id then linked[id] = true end
    end
  end


  -- 3) build targets
  local map = load_map()
  local targets = {}
  for id in pairs(linked) do
    local info = map[id]
    if info then table.insert(targets, { id = id, title = info.title, path = info.path }) end
  end

  if #targets == 0 then
    vim.notify("No outgoing links found", vim.log.levels.INFO)
    return
  end

  -- 4) single link → jump
  if #targets == 1 then
    local t = targets[1]
    local full = vault_dir .. "/" .. t.path
    write_log("goto_note: only one link, opening " .. full)
    vim.cmd("edit " .. vim.fn.fnameescape(full))
    return
  end

  -- 5) multiple → picker
  local items = {}
  for _, t in ipairs(targets) do
    table.insert(items, string.format("%s  %s", t.id, t.title))
  end
  table.sort(items)

  fzf.fzf_exec(function(cb)
    for _, entry in ipairs(items) do cb(entry) end
    cb()
  end, {
    prompt  = "Linked notes ▶︎ ",
    actions = {
      ["default"] = function(selected)
        if not selected or not selected[1] then return end
        local pick = selected[1]:match("^([0-9a-f]+)")
        local info = map[pick]
        if not info then return end
        local full = vault_dir .. "/" .. info.path
        write_log("goto_note: opening " .. full)
        vim.cmd("edit " .. vim.fn.fnameescape(full))
      end,
    },
  })
end

-- 14. Keymap: <leader>gf to go to a linked note
vim.keymap.set("n", "<leader>gf", function()
  require("nvim-notes-macros").goto_note()
end, { desc = "Go to direct outgoing link" })

write_log("=== Plugin load end ===")
return M


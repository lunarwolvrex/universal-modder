-- Shadow Wizard: a portable, original rival-memory simulation for Lua 5.4.
-- This module imports no game APIs, assets, clocks, file I/O, or randomness.
local M = {}

local SCHEMA = 1
local MAX_RIVALS = 128
local MAX_COUNTER = 1000000
local MAX_TOKEN_BYTES = 128
local MAX_NAME_BYTES = 128
local ADAPTATION_MULTIPLIER = 0.75
local MIN_ENCOUNTER_HITS = 3
local MAX_ADAPTATIONS = 2
local CATEGORIES = { "fire", "control", "force", "curse" }
local CATEGORY_SET = { fire = true, control = true, force = true, curse = true }
local OUTCOME_SET = {
    player_defeated = true,
    enemy_escaped = true,
    enemy_spared = true,
    enemy_killed = true,
}
local STATUS_SET = { available = true, in_encounter = true, dead = true }
local ROOT_FIELDS = { schema = true, profile_id = true, rivals = true }
local RIVAL_FIELDS = {
    id = true,
    display_name = true,
    rank = true,
    status = true,
    encounters = true,
    player_defeats = true,
    adaptations = true,
    spell_counts = true,
    last_outcome = true,
}

local function fail(message)
    error("rival_core: " .. message, 3)
end

local function token(value, label)
    if type(value) ~= "string" or #value == 0 or #value > MAX_TOKEN_BYTES
        or not value:match("^[A-Za-z0-9_-]+$") then
        fail(label .. " must be a 1–128 byte ASCII token [A-Za-z0-9_-]")
    end
    return value
end

local function display_name(value)
    if type(value) ~= "string" or #value == 0 or #value > MAX_NAME_BYTES
        or not value:match("%S") or value:find("[%z\1-\31\127]")
        or not utf8.len(value) then
        fail("display_name must be 1–128 bytes of nonblank UTF-8 without controls")
    end
    return value
end

local function integer(value, minimum, maximum, label)
    if type(value) ~= "number" or value ~= value or value < minimum
        or value > maximum or value % 1 ~= 0 then
        fail(label .. " is outside its integer range")
    end
    return value
end

local function plain_table(value, label)
    if type(value) ~= "table" or getmetatable(value) ~= nil then
        fail(label .. " must be a plain table")
    end
end

local function fields(value, allowed, label)
    plain_table(value, label)
    for key in pairs(value) do
        if not allowed[key] then
            fail(label .. " has an unknown field")
        end
    end
end

local function fresh_counts()
    return { fire = 0, control = 0, force = 0, curse = 0 }
end

local function dense_array_count(value, maximum, label)
    plain_table(value, label)
    local count, highest_index = 0, 0
    for index in pairs(value) do
        integer(index, 1, maximum, label .. " index")
        count = count + 1
        highest_index = math.max(highest_index, index)
    end
    if count ~= highest_index then
        fail(label .. " must be a dense array")
    end
    return count
end

local function copy_map(source)
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = value
    end
    return copy
end

local function copy_rival(source)
    local adaptations = {}
    for _, category in ipairs(CATEGORIES) do
        if source.adaptations[category] ~= nil then
            adaptations[#adaptations + 1] = category
        end
    end
    return {
        id = source.id,
        display_name = source.display_name,
        rank = source.rank,
        status = source.status,
        encounters = source.encounters,
        player_defeats = source.player_defeats,
        adaptations = adaptations,
        spell_counts = copy_map(source.spell_counts),
        last_outcome = source.last_outcome,
    }
end

local function validate_rival(source)
    fields(source, RIVAL_FIELDS, "rival")
    token(source.id, "rival id")
    display_name(source.display_name)
    integer(source.rank, 1, 5, "rank")
    integer(source.encounters, 0, MAX_COUNTER, "encounters")
    integer(source.player_defeats, 0, MAX_COUNTER, "player_defeats")
    if not STATUS_SET[source.status] then
        fail("rival status is invalid")
    end
    if source.last_outcome ~= nil and not OUTCOME_SET[source.last_outcome] then
        fail("last_outcome is invalid")
    end
    if source.rank ~= math.min(1 + source.player_defeats, 5) then
        fail("rank does not match player_defeats")
    end

    local resolved = source.encounters - (source.status == "in_encounter" and 1 or 0)
    if resolved < 0 or source.player_defeats > resolved then
        fail("encounter and player_defeats counts are inconsistent")
    end
    if (resolved == 0) ~= (source.last_outcome == nil) then
        fail("last_outcome does not match completed encounters")
    end
    if source.last_outcome == "player_defeated" and source.player_defeats == 0 then
        fail("last_outcome requires a recorded player defeat")
    end
    if source.last_outcome ~= nil and source.last_outcome ~= "player_defeated"
        and source.player_defeats >= resolved then
        fail("player_defeats leaves no encounter for last_outcome")
    end
    if (source.status == "dead") ~= (source.last_outcome == "enemy_killed") then
        fail("dead status must match enemy_killed")
    end

    local adaptation_count = dense_array_count(source.adaptations, MAX_ADAPTATIONS, "adaptations")
    local adaptations = {}
    for index = 1, adaptation_count do
        local category = source.adaptations[index]
        if type(category) ~= "string" or not CATEGORY_SET[category] then
            fail("adaptations must contain known category strings")
        end
        if adaptations[category] ~= nil then
            fail("adaptations contains a duplicate category")
        end
        adaptations[category] = ADAPTATION_MULTIPLIER
    end
    local possible_survivals = resolved - (source.status == "dead" and 1 or 0)
    if adaptation_count > MAX_ADAPTATIONS or adaptation_count > possible_survivals then
        fail("adaptation count exceeds the limit or completed survivals")
    end

    fields(source.spell_counts, CATEGORY_SET, "spell_counts")
    for _, category in ipairs(CATEGORIES) do
        integer(source.spell_counts[category], 0, MAX_COUNTER, category .. " spell count")
        if source.status ~= "in_encounter" and source.spell_counts[category] ~= 0 then
            fail("spell_counts must be zero outside an encounter")
        end
    end
    return {
        id = source.id,
        display_name = source.display_name,
        rank = source.rank,
        status = source.status,
        encounters = source.encounters,
        player_defeats = source.player_defeats,
        adaptations = adaptations,
        spell_counts = copy_map(source.spell_counts),
        last_outcome = source.last_outcome,
    }
end

local function restore(profile_id, snapshot)
    fields(snapshot, ROOT_FIELDS, "snapshot")
    if type(snapshot.schema) ~= "number" or snapshot.schema ~= SCHEMA then
        fail("snapshot schema must be 1")
    end
    token(snapshot.profile_id, "snapshot profile_id")
    if snapshot.profile_id ~= profile_id then
        fail("snapshot belongs to a different profile")
    end
    local count = dense_array_count(snapshot.rivals, MAX_RIVALS, "snapshot rivals")
    local rivals = {}
    for index = 1, count do
        local rival = validate_rival(snapshot.rivals[index])
        if rivals[rival.id] ~= nil then
            fail("snapshot contains a duplicate rival id")
        end
        rivals[rival.id] = rival
    end
    return rivals, count
end

local function presentation(rival)
    local remembered_categories = {}
    local damage_multipliers = {}
    for _, category in ipairs(CATEGORIES) do
        if rival.adaptations[category] ~= nil then
            remembered_categories[#remembered_categories + 1] = category
        end
        damage_multipliers[category] = rival.adaptations[category] or 1
    end
    return {
        id = rival.id,
        display_name = rival.display_name,
        rank = rival.rank,
        remembered_categories = remembered_categories,
        damage_multipliers = damage_multipliers,
    }
end

function M.new(profile_id, snapshot)
    token(profile_id, "profile_id")
    local rivals, rival_count = {}, 0
    if snapshot ~= nil then
        rivals, rival_count = restore(profile_id, snapshot)
    end

    -- All authoritative state remains in this closure, never on the public ledger.
    local ledger = {}
    local function require_rival(id)
        token(id, "rival id")
        if rivals[id] == nil then
            fail("rival has not been observed")
        end
        return rivals[id]
    end
    local function require_encounter(id)
        local rival = require_rival(id)
        if rival.status ~= "in_encounter" then
            fail("rival is not in an active encounter")
        end
        return rival
    end

    function ledger:observe(id, name)
        token(id, "rival id")
        display_name(name)
        local rival = rivals[id]
        if rival == nil then
            if rival_count >= MAX_RIVALS then
                fail("rival limit of 128 reached")
            end
            rival = {
                id = id,
                display_name = name,
                rank = 1,
                status = "available",
                encounters = 0,
                player_defeats = 0,
                adaptations = {},
                spell_counts = fresh_counts(),
            }
            rivals[id] = rival
            rival_count = rival_count + 1
        else
            rival.display_name = name
        end
        return copy_rival(rival)
    end

    function ledger:get(id)
        token(id, "rival id")
        return rivals[id] and copy_rival(rivals[id]) or nil
    end

    function ledger:begin_encounter(id)
        local rival = require_rival(id)
        if rival.status ~= "available" then
            fail("only an available rival can begin an encounter")
        end
        if rival.encounters >= MAX_COUNTER then
            fail("encounter counter limit reached")
        end
        rival.encounters = rival.encounters + 1
        rival.spell_counts = fresh_counts()
        rival.status = "in_encounter"
        return presentation(rival)
    end

    function ledger:hit(id, category)
        local rival = require_encounter(id)
        if type(category) ~= "string" or not CATEGORY_SET[category] then
            fail("hit category must be fire, control, force, or curse")
        end
        if rival.spell_counts[category] >= MAX_COUNTER then
            fail("spell count limit reached")
        end
        rival.spell_counts[category] = rival.spell_counts[category] + 1
        return copy_rival(rival)
    end

    function ledger:resolve(id, outcome)
        local rival = require_encounter(id)
        if type(outcome) ~= "string" or not OUTCOME_SET[outcome] then
            fail("encounter outcome is invalid")
        end

        if outcome == "enemy_killed" then
            rival.status = "dead"
        else
            if outcome == "player_defeated" then
                rival.player_defeats = rival.player_defeats + 1
                rival.rank = math.min(1 + rival.player_defeats, 5)
            end
            local total_hits, dominant, dominant_hits, adaptation_count = 0, nil, 0, 0
            for _, category in ipairs(CATEGORIES) do
                local count = rival.spell_counts[category]
                total_hits = total_hits + count
                if count > dominant_hits then
                    dominant, dominant_hits = category, count
                end
                if rival.adaptations[category] ~= nil then
                    adaptation_count = adaptation_count + 1
                end
            end
            if total_hits >= MIN_ENCOUNTER_HITS and adaptation_count < MAX_ADAPTATIONS
                and rival.adaptations[dominant] == nil then
                rival.adaptations[dominant] = ADAPTATION_MULTIPLIER
            end
            rival.status = "available"
        end
        rival.last_outcome = outcome
        rival.spell_counts = fresh_counts()
        return copy_rival(rival)
    end

    function ledger:snapshot()
        local ids = {}
        for id in pairs(rivals) do
            ids[#ids + 1] = id
        end
        table.sort(ids)
        local copies = {}
        for index, id in ipairs(ids) do
            copies[index] = copy_rival(rivals[id])
        end
        return { schema = SCHEMA, profile_id = profile_id, rivals = copies }
    end

    return ledger
end

return M

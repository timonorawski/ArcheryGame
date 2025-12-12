# x-content-type Schema Extension

Custom JSON Schema extension for annotating fields with content type hints, enabling smart editing features in the Web IDE.

## Syntax

```
x-content-type: "<type>" | "<type>|<type>" | "@ref:<category>" | "@ref:<category>:<subtype>"
```

## Content Types

### Language Types (inline code)

| Type | Description | IDE Action |
|------|-------------|------------|
| `lua` | Lua source code | Open Lua editor modal |
| `yaml` | YAML content | Open YAML editor modal |
| `data-uri` | Base64 data URI | Show preview, offer file upload |

### Reference Types (project references)

| Type | Description | IDE Action |
|------|-------------|------------|
| `@ref:behavior` | Behavior script name | Autocomplete from behaviors, link to file |
| `@ref:generator` | Generator script name | Autocomplete from generators, link to file |
| `@ref:collision_action` | Collision action name | Autocomplete from collision_actions |
| `@ref:input_action` | Input action name | Autocomplete from input_actions |
| `@ref:asset:sound` | Sound asset reference | Autocomplete from registered sounds, audio preview |
| `@ref:asset:image` | Image asset reference | Autocomplete from registered images, image preview |
| `@ref:sprite` | Sprite definition name | Autocomplete from registered sprites, preview |
| `@ref:entity_type` | Entity type name | Autocomplete from entity_types in game.yaml |
| `@ref:level` | Level file reference | Autocomplete from levels/*.yaml |

### Compound Types

Use `|` to specify multiple valid types:
```json
"x-content-type": "@ref:asset:sound|data-uri"
```

This means a field can contain either a registered sound name OR an inline data URI.

---

## Asset Registration System

Assets are registered by creating YAML definition files alongside the actual asset files. This enables:
- **Discoverability**: IDE can find and autocomplete asset names
- **Metadata**: Description, tags, dimensions for images
- **Provenance**: Track authorship, licensing, and attribution
- **Validation**: Schema validation for asset definitions

### Project Structure

```
my-game/
├── game.yaml                    # Main game config
├── levels/
│   └── level_1.yaml
├── lua/
│   └── behaviors/
│       └── bounce.lua.yaml
├── assets/
│   ├── images/
│   │   ├── background.png       # Raw image file
│   │   └── background.yaml      # Image registration
│   ├── sprites/
│   │   ├── player.yaml          # Sprite definition (references image)
│   │   └── enemy.yaml
│   └── sounds/
│       ├── explosion.wav        # Raw audio file
│       └── explosion.yaml       # Sound registration
```

### Asset Definition Files

Each asset type has its own schema, accessed via fragment references:

- **Images**: `/api/schemas/assets.schema.json#image`
- **Sprites**: `/api/schemas/assets.schema.json#sprite`
- **Sounds**: `/api/schemas/assets.schema.json#sound`

#### Image Definition (`assets/images/background.yaml`)
```yaml
name: background
description: Main game background

file: background.png
width: 800
height: 600
tags: [background, level1]

provenance:
  author: Artist Name
  license: CC-BY-4.0
  source: https://example.com/asset
```

#### Sprite Definition (`assets/sprites/player.yaml`)
```yaml
name: player
description: Player character sprite

file: ../images/spritesheet.png
x: 0
y: 0
width: 32
height: 32
transparent: [255, 0, 255]

# Animation frames (optional)
frames:
  - { x: 0, y: 0 }
  - { x: 32, y: 0 }
  - { x: 64, y: 0 }
frame_duration: 0.1
loop: true

provenance:
  author: Pixel Artist
  license: CC0
```

#### Sound Definition (`assets/sounds/explosion.yaml`)
```yaml
name: explosion
description: Explosion sound effect

file: explosion.wav
volume: 0.8
loop: false

# Random variants (optional)
variants:
  - explosion_1.wav
  - explosion_2.wav
  - explosion_3.wav

provenance:
  author: Sound Designer
  license: CC0
  source: https://freesound.org/...
```

### Provenance Metadata

All asset types support a `provenance` object for tracking attribution:

| Field | Type | Description |
|-------|------|-------------|
| `author` | string | Original creator/artist name |
| `source` | string | URL or description of origin |
| `license` | string | License identifier (CC0, CC-BY-4.0, MIT, proprietary) |
| `license_url` | uri | URL to full license text |
| `attribution` | string | Required attribution text |
| `created` | date | Date asset was created (YYYY-MM-DD) |
| `modified` | date | Date asset was last modified |
| `notes` | string | Additional provenance notes |

---

## Schema Examples

### Inline Lua Code
```json
{
  "lua": {
    "type": "string",
    "description": "Lua source code",
    "x-content-type": "lua"
  }
}
```

### Script Reference
```json
{
  "call": {
    "type": "string",
    "description": "Name of the generator to call",
    "x-content-type": "@ref:generator"
  }
}
```

### Asset Reference (sound with fallback)
```json
{
  "file": {
    "type": "string",
    "description": "Sound file path or data URI",
    "x-content-type": "@ref:asset:sound|data-uri"
  }
}
```

### Sprite Reference
```json
{
  "sprite": {
    "type": "string",
    "description": "Sprite name from asset registry",
    "x-content-type": "@ref:sprite"
  }
}
```

---

## Filetypes Registry

The IDE uses `filetypes.json` to configure file handling:

```json
{
  "filetypes": [
    {
      "id": "sprite",
      "name": "Sprite",
      "description": "A Sprite Asset Definition",
      "icon": "image",
      "filename": "{name}.yaml",
      "folder": "assets/sprites/",
      "language": "yaml",
      "schema": "/api/schemas/assets.schema.json#sprite",
      "fileMatch": ["**/assets/sprites/*.yaml"],
      "singleton": false,
      "template": "name: {name}\n..."
    }
  ]
}
```

### Schema Fragment References

The server supports fragment references to extract subschemas:

```
GET /api/schemas/assets.schema.json#sprite
```

Returns the `sprite` definition from `$defs` wrapped as a standalone schema with all internal `$ref` dependencies included.

---

## Web IDE Implementation

### Phase 1: Schema Parsing ✓

Implemented in `schemaParser.js`:

```javascript
import { schemaParser } from './schemaParser.js';

// Parse schema and extract content types
const { contentTypes, map } = await schemaParser.parse('/api/schemas/game.schema.json');

// Find content type for a specific JSON path
const info = matchPath('entity_types.player.sprite', map);
// → { path: 'entity_types.*.sprite', rawType: '@ref:sprite', parsed: {...} }
```

### Phase 2: Language Editor Integration ✓

For `lua`, `yaml` types:
- Implemented in `EmbeddedCodeEditor.svelte`
- Detects `lua:` keys in .lua.yaml files
- Opens modal with language-specific Monaco editor
- Preserves YAML structure on save

### Phase 3: Reference Autocomplete (planned)

For `@ref:*` types:
- Scan project for registered assets (YAML definition files)
- Parse game.yaml for entity_types, inline sprites
- Register Monaco completion provider per content type
- Provide hover info with "Go to definition"

### Phase 4: Asset Preview & Upload (planned)

For `@ref:asset:*` and `data-uri` types:
- Show inline preview (image thumbnail, audio player)
- File upload to convert to data-uri or create asset registration
- Asset picker modal with filtering

### Phase 5: Enhanced Navigation (planned)

- Ctrl/Cmd+Click on references to jump to definition
- "Find All References" for scripts and assets
- Outline view showing project structure

---

## Discovery API

```
GET /api/filetypes
→ Returns filetypes registry with schema URLs and templates

GET /api/schemas/{name}.json
→ Returns JSON schema with x-content-type annotations

GET /api/schemas/{name}.json#{fragment}
→ Returns subschema from $defs with dependencies

GET /api/projects/{name}/files?path=assets/
→ List asset directories and files

GET /api/projects/{name}/files/assets/sprites/player.yaml
→ Read asset definition file
```

### Future: Project References API

```
GET /api/projects/{name}/references
→ {
    "behaviors": ["bounce", "gravity"],
    "generators": ["random_position"],
    "sprites": ["player", "enemy"],
    "sounds": ["explosion", "jump"],
    "images": ["background", "spritesheet"],
    "entity_types": ["player", "enemy", "bullet"],
    "levels": ["level_1", "level_2"]
  }
```

---

## Future Extensions

- `x-content-type: "color"` - Color picker UI
- `x-content-type: "vector2"` - 2D vector editor
- `x-content-type: "rect"` - Rectangle editor with visual preview
- `x-content-type: "@ref:tag"` - Tag autocomplete from used tags
- `x-content-type: "@ref:entity_type:tag"` - Entity types with specific tag

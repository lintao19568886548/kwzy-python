# asset-geospatial-layout Specification

## Purpose
Define truthful provider-neutral spatial geometry and scoped map projections for the asset portfolio without implying unverified external GIS, CAD or BIM integrations.

## Requirements

### Requirement: Bounded provider-neutral geometry
The system SHALL accept optional GeoJSON Point or simple Polygon geometry for same-tenant park spatial nodes with explicit coordinate reference, bounded coordinates and optimistic geometry version.

#### Scenario: Valid local polygon
- **WHEN** an authorized operator saves a closed bounded polygon with coordinate reference LOCAL
- **THEN** the node stores a canonical geometry and increments its geometry version

#### Scenario: Unsafe or malformed geometry
- **WHEN** geometry is oversized, unclosed, out of range, nested beyond the allowed shape or includes an unsupported type
- **THEN** the command fails without altering prior geometry

### Requirement: Scoped truthful map projection
The system SHALL return a FeatureCollection containing only visible stored geometries and current inventory aggregates, plus explicit counts for inventory whose space has no geometry.

#### Scenario: Unmapped building
- **WHEN** a visible building has units but no stored geometry
- **THEN** its units contribute to unmapped counts and are not assigned invented coordinates

### Requirement: No false GIS CAD or BIM claim
Geometry APIs and UI SHALL identify their coordinate reference and provider status and SHALL NOT report basemap, CAD or BIM synchronization without a separately verified adapter result.

#### Scenario: Local schematic displayed
- **WHEN** LOCAL coordinates are rendered in the PC map mode
- **THEN** the page labels the view as a park schematic and external provider status as not connected

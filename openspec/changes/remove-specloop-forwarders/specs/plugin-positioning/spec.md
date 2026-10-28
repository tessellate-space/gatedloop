## REMOVED Requirements

### Requirement: The earlier name is read loudly for one release

**Reason**: Its one release, 0.8.x, is over. From 0.9.0 the earlier name is refused, not read.

**Migration**: Run `gates migrate-name` before upgrading, and require `gatedloop/<gate>` in branch protection instead of `specloop/<gate>`.

## ADDED Requirements

### Requirement: The earlier name is refused after its release

From 0.9.0 the shim SHALL read only the `gatedloop` identifiers, and `gates marker
publish` SHALL post only `gatedloop/<gate>`. A project that still holds `.specloop/`
SHALL be refused by every command except `gates doctor` and `gates migrate-name`, and
the refusal SHALL name `gates migrate-name`.

#### Scenario: A project never migrated

- **WHEN** a project holding only `.specloop/` runs any gate after upgrading to 0.9.0
- **THEN** the shim refuses, naming `gates migrate-name`, and writes no `.gatedloop/`

#### Scenario: Publishing a status

- **WHEN** `gates marker publish ci` runs on a green tree
- **THEN** only `gatedloop/ci` is posted

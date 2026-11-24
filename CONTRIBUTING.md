# Contributing

Thank you for helping improve the Restaurant Management Platform. Keep each change focused, tested, and easy to review.

## Development workflow

1. Update your local `main` branch:

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

2. Create a focused branch using one of these prefixes:

   - `feat/` for user-facing functionality
   - `fix/` for bug fixes
   - `test/` for test coverage
   - `docs/` for documentation
   - `ci/` for automation
   - `refactor/` for behavior-preserving code changes
   - `chore/` for maintenance

3. Make one cohesive change. Avoid mixing unrelated refactors, dependency updates, and product behavior in the same pull request.
4. Run the relevant checks listed below.
5. Commit the change and open a pull request against `main`.

## Local setup

The supported development environment uses Docker Compose:

```bash
make up
make health
```

Useful commands:

```bash
make logs
make seed
make down
```

Run `make help` to see every available command.

## Quality checks

Run the smallest relevant check while developing, then run the full suite before requesting review:

```bash
make lint
make typecheck
make test
make build
```

The complete local quality gate is:

```bash
make check
```

For changes to critical user journeys, start the application and run the acceptance suite:

```bash
make e2e
```

For Terraform changes, also run:

```bash
make terraform-check
```

## Commit messages

Use a concise Conventional Commit subject:

```text
feat(reservations): add table availability filter
fix(groups): prevent duplicate participant orders
test(reports): cover empty analytics export
ci: cancel stale workflow runs
```

Write in the imperative mood, keep the subject focused, and explain non-obvious decisions in the commit body.

## Pull requests

- Describe what changed and why.
- Link the related issue with `Closes #123` when applicable.
- Include screenshots for visible UI changes.
- Document new environment variables, migrations, and deployment considerations.
- Keep generated files and unrelated formatting out of the diff.
- Confirm that the applicable CI checks pass.

Reviewers should be able to understand and validate the change without reconstructing its intent from the code.

## Security

Never commit passwords, API keys, access tokens, private keys, `.env` files, Terraform state, or production customer data. Use example values in documentation and report suspected vulnerabilities privately to the repository owner.

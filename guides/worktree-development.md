# Worktree Development

## When to Use Worktrees

Use git worktrees when working on parallel tasks that touch overlapping files, or when you need to keep an in-progress feature isolated while reviewing another branch.

## Creating a Worktree

```bash
# Create a worktree for a new feature branch
git worktree add ../ai-rca-feature-xyz feature/xyz

# Or create with a new branch
git worktree add -b feature/new-thing ../ai-rca-new-thing develop
```

## Worktree Layout

```
~/Documents/i2i/idea/
  ai-rca/              # main worktree (develop)
  ai-rca-feature-xyz/  # feature worktree
```

## In Each Worktree

- The `.venv` is shared — no need to reinstall
- Run tests from the worktree root: `cd ../ai-rca-feature-xyz && pytest`
- `.beads/` state is per-worktree — each has its own execution state

## Cleanup

```bash
# Remove worktree when done
git worktree remove ../ai-rca-feature-xyz

# Prune stale worktree references
git worktree prune
```

## metaswarm in Worktrees

The `EnterWorktree` / `ExitWorktree` tools create isolated worktrees automatically. After the agent finishes, the worktree is cleaned up if no changes were made; otherwise the path and branch are returned.

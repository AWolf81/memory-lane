# Poetry vs pip Decision

**Date:** 2026-01-15
**Decision:** Stick with pip + requirements.txt
**Confidence:** High

---

## Research Summary

### Poetry Advantages (2026)
- ✅ Automatic dependency resolution
- ✅ Lock files (poetry.lock) for reproducibility
- ✅ Separates dev/prod dependencies cleanly
- ✅ Modern, widely adopted
- ✅ Better for team projects
- ✅ PEP 517/518 compliant
- ✅ Publishing to PyPI simplified

### Poetry Disadvantages
- ❌ Additional installation step (curl script or pip install poetry)
- ❌ Heavier tooling overhead
- ❌ Learning curve for new users
- ❌ Overkill for simple projects
- ❌ Can be slower than pip for simple installs

### pip + requirements.txt Advantages
- ✅ Built into Python (always available)
- ✅ Familiar to all Python developers
- ✅ Simple, minimal approach
- ✅ Works everywhere
- ✅ No extra installation needed

### pip + requirements.txt Disadvantages
- ❌ No automatic dependency resolution
- ❌ No built-in lock files (need pip-tools for that)
- ❌ Manual dev/prod separation
- ❌ Version conflicts harder to debug

---

## Our Context

### MemoryLane Specifics

**Production Dependencies:**
```python
# requirements.txt
# NONE - Pure Python 3.8+ implementation
```

**Development Dependencies:**
```python
# requirements-dev.txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
```

**Key Facts:**
1. ✅ **Zero production dependencies**
2. ✅ Only 3 dev dependencies (all pytest-related)
3. ✅ No complex dependency trees
4. ✅ No version conflicts possible
5. ✅ Following ace-system-skill proven pattern

---

## Decision Matrix

| Factor | Poetry | pip | Winner |
|--------|--------|-----|--------|
| **Setup Complexity** | Requires Poetry install | Built-in | **pip** |
| **Dependency Count** | Overkill for 0 deps | Perfect | **pip** |
| **User Familiarity** | Growing | Universal | **pip** |
| **Installation Speed** | Slower | Faster | **pip** |
| **Lock Files** | Automatic | Manual (pip-freeze) | Poetry |
| **Dev/Prod Split** | Clean | Manual split files | Poetry |
| **CI/CD Integration** | Needs Poetry in CI | Works everywhere | **pip** |
| **Pattern Consistency** | New approach | Matches ace-skill | **pip** |

**Score: pip wins 6-2**

---

## Decision: Stick with pip

### Rationale

1. **Zero Production Dependencies**
   - No complex dependency resolution needed
   - No version conflicts possible
   - Poetry's main benefit doesn't apply

2. **Simpler User Experience**
   - Users don't need to install Poetry
   - Standard Python workflow
   - Lower barrier to entry

3. **Pattern Consistency**
   - ace-system-skill uses requirements.txt
   - Proven approach for Claude skills
   - Easier to understand for contributors

4. **Faster Installation**
   - No Poetry installation step
   - Direct pip install
   - Works in all environments

5. **Adequate for Our Needs**
   - Only 3 dev dependencies
   - No complex resolution needed
   - Manual dev/prod split is fine

### Migration Path

If we later add production dependencies, we can migrate:

```bash
# Convert to Poetry (future)
poetry init
poetry add <package>
poetry lock
```

But for MVP with zero deps, pip is perfect.

---

## Implementation

### Current Setup

```bash
# Production (none)
pip install -r requirements.txt  # Empty file

# Development
pip install -r requirements-dev.txt

# Or in one step
pip install pytest pytest-cov pytest-mock
```

### If We Add Dependencies Later

We'll reconsider Poetry when:
1. We add ≥5 production dependencies
2. Version conflicts become an issue
3. Lock file management becomes critical
4. Team size grows (>3 contributors)

---

## Conclusion

**For MemoryLane v0.1.0 with zero production dependencies, pip + requirements.txt is the right choice.**

Poetry is excellent for complex projects, but we don't need that complexity yet. We can always migrate later if needed.

---

## References

- [Poetry vs Pip: Choosing the Right Python Package Manager](https://betterstack.com/community/guides/scaling-python/poetry-vs-pip/)
- [Python Packaging Best Practices 2026](https://dasroot.net/posts/2026/01/python-packaging-best-practices-setuptools-poetry-hatch/)
- [Dependency Management With Python Poetry](https://realpython.com/dependency-management-python-poetry/)
- [Do not use requirements.txt (Quanttype)](https://quanttype.net/posts/2023-10-31-do-not-use-requirements.txt.html)

**Note:** The "do not use requirements.txt" article makes valid points for complex projects with many dependencies. Our project has zero production dependencies, making those concerns moot.

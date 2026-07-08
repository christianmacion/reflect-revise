# Choosing a Build Tool

This post will explore the trade-offs between common build tools for a mid-size codebase.

The first thing to know is that no tool is perfect. Some teams want speed, others want plugin support, and a few want both. It's worth noting that the defaults matter more than most people think, because the defaults are what new contributors hit on day one.

Moreover, caching behavior differs a lot between tools. Furthermore, the way each tool handles incremental builds will shape your CI bill. We benchmarked three options on a 40-package monorepo and the spread was wide.

The point is simple. Pick the tool your team will actually configure, measure the cold-build and warm-build times yourself, and revisit the choice once a quarter. A fast tool nobody tunes is slower than a slow tool that is tuned well.

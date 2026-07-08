# Notes on Caching

The cache stores recent results in memory for fast reads. The cache evicts old entries when it runs out of room. The cache uses a least-recently-used policy by default here. The cache can be tuned with a size limit and a time limit too.

Reads check the cache first before they hit the slower backing store. Writes update the cache and the store at the same time for safety. Misses fall through to the store and then fill the cache again. Hits return the stored value right away without any extra work.

The system tracks a hit rate so you can see how well it works. The hit rate climbs as the working set fits inside the cache size. The hit rate falls when the working set grows past the cache size. The rate is the main number to watch when you tune the limits.

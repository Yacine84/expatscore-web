# =============================================================================
# MODIFIED FUNCTIONS FOR REDDITWORKER V6.7 (403 FIX + OPTIMIZATION)
# =============================================================================

# Global counter for testing mode (place near top of file with other globals)
test_cycles_remaining = 2  # First 2 cycles use fast testing interval

# =============================================================================
# TIME-ADAPTIVE ACTOR INPUT (Fixes 403 + Maximizes Harvest)
# =============================================================================

def scrape_cycle(warmup: bool) -> int:
    """
    v6.7.1 HOTFIX:
    - Removed urls parameter (403 Forbidden fix)
    - Dynamic time window: "all" for initial cycles, then "day"
    - Enhanced Shadow Thread detection logic
    """
    global test_cycles_remaining
    
    mode_label = "🔥 WARMUP" if warmup else "🎯 INTELLIGENCE CYCLE"
    
    log.info("=" * 70)
    log.info(f"[Reddit] {mode_label} | {datetime.now(ZoneInfo('Europe/Berlin')).strftime('%Y-%m-%d %H:%M:%S')} CET")
    log.info(f"[Apify] Actor: {APIFY_ACTOR_ID} | 403-FIXED MODE (No URLs param)")
    log.info("=" * 70)

    # Build search query with random keyword sampling
    sample_size = min(5, len(KEYWORDS))
    random_keywords = random.sample(KEYWORDS, sample_size)
    quoted_keywords = [f'"{kw}"' if " " in kw else kw for kw in random_keywords]
    keyword_clause = "(" + " OR ".join(quoted_keywords) + ")"
    subreddit_clause = "(" + " OR ".join([f"subreddit:{sub}" for sub in SUBREDDITS]) + ")"
    final_query = f"{keyword_clause} {subreddit_clause}"
    
    log.info(f"  🔍 Search Query: {final_query[:180]}...")
    log.info(f"  🧠 Emotional Markers Active: {len(EMOTIONAL_MARKERS)} crisis signals")

    # DETERMINE TIME WINDOW: First 2 cycles use "all" (historical), then "day"
    time_window = "all" if test_cycles_remaining > 0 else "day"
    if time_window == "all":
        log.info("  📚 TIME WINDOW: ALL (Historical Shadow Thread Harvesting)")
    else:
        log.info("  ⏰ TIME WINDOW: DAY (Last 24h only)")

    # v6.7.1 Actor Input: 403-FIXED (No urls parameter)
    actor_input = {
        "queries": [final_query],
        "searchMode": "relevance",
        "maxResults": MAX_RESULTS_PER_CYCLE,
        "sort": "new",
        "type": "post",
        "time": time_window,  # Dynamic: "all" for first 2 cycles, then "day"
        "scrapeComments": True,  # SHADOW THREAD: Active
        "includeNSFW": False,
        # "urls": []  # REMOVED: Causes 403 Forbidden
    }

    try:
        log.info("  🚀 Deploying Apify (403-Fixed | Shadow Thread Mode)...")
        run = apify_client.actor(APIFY_ACTOR_ID).call(run_input=actor_input)
        dataset_id = run["defaultDatasetId"]
        dataset_items = list(apify_client.dataset(dataset_id).iterate_items())
        log.info(f"  ✅ Extraction complete – {len(dataset_items)} items (posts + shadow threads)")
    except Exception as e:
        log.error(f"  ✖ Apify actor call failed: {e}")
        return 0

    if not dataset_items:
        log.info("  ⚠ Dataset empty – adjusting query parameters for next cycle")
        return 0

    sent_count = 0
    processed_count = 0
    
    # Cycle-level deduplication
    cycle_seen_posts = set()
    cycle_seen_comments = set()

    for item in dataset_items:
        # =================================================================
        # SHADOW THREAD DETECTION LOGIC (v6.7.1 Enhanced)
        # =================================================================
        
        # Method 1: Explicit type field (most reliable)
        item_type = item.get("type", "").lower()
        is_comment = item_type == "comment"
        
        # Method 2: Check for comment-specific fields (fallback)
        if not is_comment:
            has_comment_id = "commentId" in item or item.get("id", "").startswith("t1_")
            has_parent = "parentId" in item or "parent_id" in item
            is_comment = has_comment_id and has_parent
        
        # Method 3: Check body vs selftext (posts have selftext, comments have body)
        if not is_comment:
            has_body = bool(item.get("body", "").strip())
            lacks_selftext = not bool(item.get("selftext", "").strip())
            if has_body and lacks_selftext and item.get("depth") is not None:
                is_comment = True
        
        # Process based on type
        if is_comment:
            # SHADOW THREAD (COMMENT) PROCESSING
            comment_id = item.get("commentId") or item.get("id", "").replace("t1_", "")
            if not comment_id or comment_id in seen_comment_ids or comment_id in cycle_seen_comments:
                continue
            
            author = item.get("author", "[deleted]")
            body = item.get("body", item.get("text", "")).strip()
            
            # Skip deleted/removed
            if not body or body in ["[deleted]", "[removed]", "[ Deleted ]"]:
                continue
            
            content_for_analysis = body
            unique_id = comment_id
            cycle_seen_comments.add(comment_id)
            
            # Build permalink from parent if available
            permalink = item.get("url", "")
            if not permalink and "postId" in item:
                permalink = f"https://www.reddit.com/r/{item.get('subreddit', '')}/comments/{item['postId']}/comment/{comment_id}"
            
            subreddit = item.get("subreddit", "")
            created_utc = item.get("createdUtc", 0)
            parent_id = item.get("parentId", item.get("parent_id", ""))
            depth = item.get("depth", 0)
            
            log.debug(f"   🧵 Shadow Thread detected | Depth: {depth} | ID: {comment_id[:8]}...")
            
        else:
            # STANDARD POST PROCESSING
            post_id = item.get("id", "").replace("t3_", "")
            if not post_id or post_id in seen_post_ids or post_id in cycle_seen_posts:
                continue
            
            title = item.get("title", "")
            body = item.get("selftext", item.get("content", ""))
            author = item.get("author", "[deleted]")
            subreddit = item.get("subreddit", "")
            permalink = item.get("url", "")
            created_utc = item.get("createdUtc", 0)
            
            if permalink and not permalink.startswith("http"):
                permalink = f"https://www.reddit.com{permalink}"
            
            content_for_analysis = f"{title}\n\n{body}".strip()
            unique_id = post_id
            cycle_seen_posts.add(post_id)
            parent_id = None  # Posts have no parent
            depth = 0
        
        # ==========================================
        # STAGE 1: Heuristic Pre-Filter
        # ==========================================
        passes_heuristic, reason = heuristic_pre_check(content_for_analysis)
        if not passes_heuristic:
            log.debug(f"   🚫 Filtered ({reason}): {unique_id[:20]}...")
            # Mark as seen to avoid reprocessing
            if is_comment:
                seen_comment_ids.add(comment_id)
            else:
                seen_post_ids.add(post_id)
            continue
        
        # ==========================================
        # KEYWORD MATCHING (Shadow threads often have context in parent)
        # ==========================================
        combined_text = content_for_analysis.lower()
        matched_keywords = [kw for kw in KEYWORDS if kw.lower() in combined_text]
        
        if not matched_keywords:
            if is_comment:
                seen_comment_ids.add(comment_id)
            else:
                seen_post_ids.add(post_id)
            continue
        
        # ==========================================
        # EMOTIONAL VELOCITY (Enhanced for Comments)
        # ==========================================
        # Comments often contain more raw emotion than posts
        emotional_velocity, is_priority = calculate_emotional_velocity(content_for_analysis)
        
        # Boost priority for deep thread comments (indicates active engagement)
        if is_comment and depth and depth > 1:
            emotional_velocity += 5  # Deep engagement bonus
        
        # ==========================================
        # STAGE 2: Groq LLM Scoring
        # ==========================================
        groq_score, confirmed_priority, reasoning = score_lead(
            content=content_for_analysis,
            matched_keywords=matched_keywords,
            source="reddit_comment" if is_comment else "reddit_post",
            emotional_velocity=emotional_velocity
        )
        
        final_priority = is_priority or confirmed_priority
        
        if groq_score < MIN_GROQ_SCORE:
            log.info(f"   🔕 Score {groq_score}/100 – Skipped")
            if is_comment:
                seen_comment_ids.add(comment_id)
            else:
                seen_post_ids.add(post_id)
            continue
        
        # ==========================================
        # PAYLOAD CONSTRUCTION (v6.7.1 Enhanced)
        # ==========================================
        payload = {
            "source": "reddit_shadow_thread" if is_comment else "reddit_post",
            "user": author,
            "post_id": unique_id,
            "parent_id": parent_id,
            "is_shadow_thread": is_comment,
            "thread_depth": depth if is_comment else 0,
            "content_preview": content_for_analysis[:200].replace('\n', ' '),
            "full_text": content_for_analysis[:3000],
            "title": "Comment Reply" if is_comment else (item.get("title", "") if not is_comment else ""),
            "groq_score": groq_score,
            "emotional_velocity": emotional_velocity,
            "priority": final_priority,
            "matched_keywords": matched_keywords,
            "keyword_count": len(matched_keywords),
            "link": permalink,
            "subreddit": subreddit,
            "created_utc": int(created_utc) if created_utc else 0,
            "scraped_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(),
            "scoring_reasoning": reasoning,
            "harvest_mode": "historical" if time_window == "all" else "recent"
        }

        success = send_to_n8n(payload)
        if success:
            sent_count += 1
            if is_comment:
                seen_comment_ids.add(comment_id)
            else:
                seen_post_ids.add(post_id)
        
        processed_count += 1
        time.sleep(random.uniform(0.5, 1.5))

    # Decrement test counter after cycle completion
    if test_cycles_remaining > 0:
        test_cycles_remaining -= 1
        log.info(f"  🔧 TEST MODE: {test_cycles_remaining} fast cycles remaining")

    log.info(f"  📊 Cycle Stats | Processed: {processed_count} | Sent: {sent_count} | Shadows: {sum(1 for _ in range(processed_count) if is_comment)}")
    return sent_count


# =============================================================================
# ADAPTIVE INTERVAL ENGINE (Testing Mode + Aggressive Jitter)
# =============================================================================

def get_interval() -> float:
    """
    v6.7.1: Dynamic interval engine
    - First 2 cycles: 1-3 minutes (fast testing)
    - Cycle 3+: Aggressive 8-15 min jitter with -3 to +8 variance
    """
    global test_cycles_remaining
    
    if test_cycles_remaining > 0:
        # TESTING MODE: 1-3 minutes for rapid verification
        fast_minutes = random.uniform(1, 3)
        log.info(f"  ⏳ [TEST MODE] Next cycle in {fast_minutes:.1f} min ({test_cycles_remaining} fast cycles left)")
        return fast_minutes * 60
    else:
        # PRODUCTION MODE: Aggressive anti-detection jitter
        base_minutes = random.uniform(8, 15)
        jitter = random.uniform(-3, 8)  # Asymmetric drift
        total_minutes = max(5, base_minutes + jitter)  # Safety floor 5 min
        
        log.info(f"  ⏳ [PRODUCTION] Next cycle in {total_minutes:.1f} min (base: {base_minutes:.1f} | jitter: {jitter:+.1f})")
        return total_minutes * 60
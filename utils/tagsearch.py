import difflib

def search_tags(tags: dict, query: str) -> list:
    """
    Searches for tags that match the query.
    Returns a list of matching tag names.
    """
    tag_names = list(tags.keys())
    
    # 1. Exact match (case-insensitive) - usually handled by caller but good to have
    exact = [name for name in tag_names if name.lower() == query.lower()]
    
    # 2. Starts with query
    starts_with = [name for name in tag_names if name.lower().startswith(query.lower()) and name not in exact]
    
    # 3. Contains query
    contains = [name for name in tag_names if query.lower() in name.lower() and name not in exact and name not in starts_with]
    
    matches = exact + starts_with + contains
    
    # 4. If strict matches are few, try fuzzy
    if len(matches) < 5:
        fuzzy = difflib.get_close_matches(query, tag_names, n=5, cutoff=0.6)
        # Add simpler fuzzy matches if they aren't already included
        for f in fuzzy:
            if f not in matches:
                matches.append(f)
        
    return matches[:15] # Return top 15 matches

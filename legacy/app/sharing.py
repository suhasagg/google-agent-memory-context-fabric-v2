def validate_share(a,b,layers,scope):
 if a==b:raise ValueError("distinct agents required")
 if "working" in layers:raise ValueError("working memory cannot be shared")
 return {"from":a,"to":b,"layers":layers,"scope":scope}

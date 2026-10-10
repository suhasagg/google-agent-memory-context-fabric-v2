from app.embeddings import embed,cosine
def detect(existing,new):
 return [{"memory_id":str(m.id),"similarity":cosine(embed(m.content),embed(new)),"resolution":"REVISION_OR_REVIEW"} for m in existing if cosine(embed(m.content),embed(new))>.45]

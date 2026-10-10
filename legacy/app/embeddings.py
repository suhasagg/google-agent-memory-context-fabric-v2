import hashlib,math
def embed(text,dim=64):
 v=[0.0]*dim
 for x in text.lower().split():v[int(hashlib.sha256(x.encode()).hexdigest(),16)%dim]+=1
 n=math.sqrt(sum(i*i for i in v)) or 1
 return [i/n for i in v]
def cosine(a,b):return sum(x*y for x,y in zip(a,b))

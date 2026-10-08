def masks(words):
    out=[]
    for word in words:
        if not isinstance(word,str) or any(not 'a'<=c<='z' for c in word):raise ValueError('lowercase words required')
        mask=0;valid=True
        for c in word:
            bit=1<<(ord(c)-97)
            if mask&bit:valid=False
            mask|=bit
        out.append(mask if valid else None)
    return out

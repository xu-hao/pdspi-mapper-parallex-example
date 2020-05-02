from oslash import Left, Right    

def isBundle(bundle):
    return isinstance(bundle, dict) and "resourceType" in bundle and bundle["resourceType"] == "Bundle"

    
def bundle(records):
    return {
        "resourceType": "Bundle",
        "entry": list(map(lambda record: {
            "resource": record
        }, records))
    }


def unbundle(bundle):
    if isBundle(bundle):
        return Right(list(map(lambda a : a["resource"], bundle.get("entry", []))))
    else:
        return Left(str(bundle) + " is not a bundle")



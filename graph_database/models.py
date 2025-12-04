from neomodel.core import StructuredNode
from neomodel.properties import (
    DateProperty,
    StringProperty,
    UniqueIdProperty,
)
from neomodel.relationship_manager import RelationshipFrom, RelationshipTo


# NOTE: JSON format what it will be returning
""" json

{
    title : "title of research paper",
    authers : ["john doe","vladimir putin","heatler"]
	link : "https://link-of-researchpaper.com",
	description:"A huge descritption of that research paper",
	images : [
	    {
		    image_link : "https://image.jpg",
			image_dec : "description of that image"
		},
		{
			image_link : "https://image2.jpg",
			image_dec : "another one description"
		}
	],
	cites : [
	    {
			title : "referenvce research paper",
			link : "https://another-link.com",
            authors : ["john doe","toby maguire"]
		},
		{
		    title : "referenvce research paper",
			link : "https://another-link.com",
            authors : ["john doe","toby maguire"]
		},
        {
			title : "referenvce research paper",
			link : "https://another-link.com",
            authors : ["john doe","toby maguire"]
		},
	]
}

"""
# OPTIMIZE: Dont know if this is ideal or not


class Author(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(required=True, unique_index=True)
    # Reverse relationships
    papers = RelationshipFrom("Paper", "AUTHORED_BY")
    cited_papers = RelationshipFrom("Cites", "CONTRIBUTED_BY")


class Visuals(StructuredNode):
    uid = UniqueIdProperty()
    image_link = StringProperty(unique_index=True, required=True)
    image_dec = StringProperty()
    # Reverse relationship
    paper = RelationshipFrom("Paper", "HAS_IMAGE")


class Cites(StructuredNode):
    uid = UniqueIdProperty()
    title = StringProperty(required=True)
    url = StringProperty()
    # Relationships
    authors = RelationshipTo(Author, "CONTRIBUTED_BY")
    cited_by_paper = RelationshipFrom("Paper", "CITES")


class Paper(StructuredNode):
    uid = UniqueIdProperty()
    title = StringProperty(unique_index=True, required=True)
    abstract = StringProperty()
    year = DateProperty()
    url = StringProperty()
    # Relationships
    authors = RelationshipTo(Author, "AUTHORED_BY")
    images = RelationshipTo(Visuals, "HAS_IMAGE")
    cites = RelationshipTo(Cites, "CITES")

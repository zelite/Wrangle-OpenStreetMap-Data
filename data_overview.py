from __future__ import print_function, unicode_literals, division
import os
import pprint
from pymongo import MongoClient
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams.update({'figure.autolayout': True}) # adjust plot areas automatically

def get_db(db_name):
    """ Connect to MongoDB and return db object

    :param db_name: database name
    :return: database object
    """
    client = MongoClient('localhost:27017')
    db = client[db_name]
    return db


def top_x_amenities(db, x):
    """ Get count of top x amenities types from the data

    :param db: database name
    :param x: number of amenities type to return
    :return: list of dictionaries with the count of top x amenities.
    """
    pipeline = [{"$match": {"amenity": {"$exists": True}}},
                {"$group": {"_id": "$amenity", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": x}]
    return aggregate(db, pipeline)

def aggregate(db, pipeline):
    """ Given a pipeline, return a list
    with the results of running the pipeline in the MongoDB

    :param db: database name
    :param pipeline: list of MongoDB documents with pipeline commands
    :return: list of results
    """
    return [doc for doc in db.goettingen.aggregate(pipeline)]


def plot_top_x_amenities(db, x, where="screen"):
    """ Make a bar plot of the top x amenities.

    :param db: mongo db object
    :param x: number of top amenity types to return
    :param where: "screen" (default) or "file". Where you want the plot?
                  "screen": shows plot via plt.show().
                  "file": saves plot in working dir as a png.
    """
    top_x_df = pd.DataFrame(top_x_amenities(db, x))
    plot = sns.barplot(x="count", y="_id", data=top_x_df, color=sns.color_palette()[0])
    plot.set(xlabel ="count", ylabel="amenity")
    if where=="file":
        plt.savefig("top_"+str(x)+"amenitys.png")
    elif where=="screen":
        plt.show(plot)
    plt.close()

def amenities_accessibility(db, amenities):
    """ Return the count of amenities grouped by wheelchair accessibility.

    :param db: db
    :param amenities: list of amenities
    :return: list of results
    """
    pipeline = [{"$match": {"amenity": {"$in": amenities}}},
                {"$group": {"_id": {"amenity": "$amenity",
                                    "wheelchair": "$wheelchair"},
                                    "count": {"$sum": 1}}}]
    return aggregate(db, pipeline)

def expand_ids(dict_):
    """ Flattens the dictionary, so that the
    keys inside "_id" are at the same level as the
    remaining keys.

    :param dict_: dictionary with a subdictionary under the "_id" key.
    :return: flat dictionary
    """
    r_dict = dict_.copy()
    r_dict.pop("_id")
    ids = dict_["_id"]
    r_dict.update(ids)
    return r_dict

def plot_amenities_and_access(db, amenities_list, where="screen"):
    """ Makes a bar plot with the acessibility information
    for each amenity type.

    :param db: database name
    :param amenities_list: list of amenities to include in plot
    :param where: "screen" (default) or "file". Where you want the plot?
                  "screen": shows plot via plt.show().
                  "file": saves plot in working dir as a png.
    """
    amenities_access = amenities_accessibility(db, amenities_list)
    amenities_access = pd.DataFrame([expand_ids(el) for el in amenities_access])
    amenities_access.fillna("no data", inplace=True)
    amenities_access_percentage = (amenities_access.groupby(["amenity", "wheelchair"]).
                                   aggregate({"count": "sum"}).
                                   groupby(level=0).
                                   apply(lambda x: 100*x/x.sum())) #http://stackoverflow.com/a/23377232/1952996
    plot = sns.factorplot(x="count", y="amenity",
                       hue="wheelchair",
                       data=amenities_access_percentage.reset_index(),
                       kind="bar",
                       hue_order=["yes", "limited", "no", "no data"],
                       legend=False,
                       aspect=2)
    plot.set(xlabel ="wheelchair accessibility (%)", ylabel="amenity")
    plt.legend(loc="upper right")
    if where=="file":
        plt.savefig("amenities_and_access.png")
    elif where=="screen":
        plt.show(plot)
    plt.close()



if __name__ == "__main__":
    print("# File sizes:")
    print("goettingen.osm size:", os.path.getsize("goettingen.osm"), "bytes")
    print("goettingen.osm.json size:", os.path.getsize("goettingen.osm.json"), "bytes")
    db = get_db("maps")
    print("# Number of unique users:")
    print(len(db.goettingen.distinct("created.user")))
    print("# Number of ways:")
    print(db.goettingen.find({"type":"way"}).count())
    print("# Number of nodes:")
    print(db.goettingen.find({"type":"node"}).count())
    print("# Number of vending machines with food:")
    print(db.goettingen.find({"amenity":"vending_machine",
                              "vending": {"$in": ["food", "food;drinks"]}
                              }).count())
    plot_top_x_amenities(db, 20, where="file")
    amenities_to_explore = ["restaurant", "kindergarten", "fast_food",
                            "doctors", "cafe", "place_of_worship", "school"]
    plot_amenities_and_access(db, amenities_to_explore, where="file")


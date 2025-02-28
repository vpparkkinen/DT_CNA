import pandas as pd
import numpy as np
import os
import os.path
import re
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

nfil = len([1 for x in list(os.scandir("data")) if x.is_file()])

# load data sets
dats = []
for f in range(1, nfil+1):
  dats.append(pd.read_csv("data/dat"+str(f)+".csv", sep = ";"))

# increase N
dats = [pd.concat([i] * 100, ignore_index=True) for i in dats]

feature_names = ["B", "C", "D", "E", "F"]
outcome = "A"

# store outcomes ('y') and exo vars/predictors ('X') to separate lists, .value for getting numpy arrays to be used in training
Xs = [x.iloc[:, 1:].values for x in dats]
ys = [x.iloc[:, 0].values for x in dats]

# 80%/20% train/test splits
# -> list of lists where element 0 is X train,
# 1 is X test, 2 is y train, 3 y test
tt_splits = [train_test_split(x, y, test_size=0.2, random_state=1) for x, y in zip(Xs, ys)]

# that's awful to work with, dict to organize the t/t splits so that single magic number typo later won't break everything
trains_tests = dict(zip(["X_train", "X_test", "y_train", "y_test"],  map(list, zip(*tt_splits))))

# Note: We want to interpret the trees as explanations of the
# outcome, and check if those explanations are correct by
# comparing to the data-generating causal structure. So
# we don't really care about the model predictions
# at this point -> an incorrect explanation might
# predict false outcomes, but also an _incomplete_
# _correct_ explanation would. Similarly, a model/explanation
# that is
# incorrect by way of including redundant parts might make
# better predictions than an incomplete correct model. Anyway,
# we don't really need the test sets here, but there they are
# if we want to do something with them later.

# model init
dt_cl = DecisionTreeClassifier(criterion='entropy', max_depth=7, random_state=1) # no idea if the params make sense

# fit models
fitted = [dt_cl.fit(x, y) for x, y in zip(trains_tests["X_train"], trains_tests["y_train"])]

# func for getting a dict of tree paths
# to do: ditch the 0-paths
def get_decision_paths(tree, feature_names):
    left = tree.tree_.children_left
    right = tree.tree_.children_right
    threshold = tree.tree_.threshold
    features = [feature_names[i] if i != -2 else "Leaf" for i in tree.tree_.feature]
    value = tree.tree_.value
    paths_by_class = {}

    def recurse(node, path):
       # print(node)
       # print(path)
        if left[node] == -1 and right[node] == -1:  # Leaf node
            predicted_class = np.argmax(value[node])  # Get class with highest probability
            #path.append(f"Class: {predicted_class}")
            # Store paths by class
            if predicted_class not in paths_by_class:
                paths_by_class[predicted_class] = []
            paths_by_class[predicted_class].append("*".join(path))
        else:
            if left[node] != -1:
                recurse(left[node], path + [f"{features[node]} <= {threshold[node]:.2f}"])
            if right[node] != -1:
                recurse(right[node], path + [f"{features[node]} > {threshold[node]:.2f}"])

    recurse(0, [])
    return paths_by_class[1] # return only paths for out present

# replace 'X <= 0.50' w/ 'x' and 'X > 0.50' w/ X.
def eq_to_lits(input_string):
      pattern_leq = r"([A-Za-z])\s*<=\s*0\.50"
      pattern_gt = r"([A-Za-z])\s*>\s*0\.50"
      output_string = re.sub(pattern_leq, lambda m: m.group(1).lower(), input_string)
      output_string = re.sub(pattern_gt, lambda m: m.group(1).upper(), output_string)
      return output_string

# for translating from fitted dt to cna asf
def dt_to_cna(dt, feature_names, outcome):
    paths = get_decision_paths(dt, feature_names=feature_names)
    suffs = [eq_to_lits(x) for x in paths]
    return "+".join(suffs)+"<->"+outcome

# convert fitted dts to cna asfs
mods = [dt_to_cna(x, feature_names, outcome) for x in fitted]

# write mods to file
np.savetxt("dt_results.txt", mods, delimiter="\n", fmt="%s")

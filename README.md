# Using the libraries

To be able to add this to python library need to add it to `PYTHONPATH` in windows environment variables

# Reloading libraries

It is always good to get into a habit of providing reusable code
This is achieved in the form of the custom library `myutils`
However, the code is constantly being edited
Thus, must use `importlib.reload` on the modules being edited
For example, take a test function with one arg

```python
// myutils.generic
def testfunction(a):
    pass
```
If this is imported
```python
from myutils import generic
help(generic.testfunction)
```
It would print something like
> Help on function testfunction in module myutils.generic:
> testfunction(a)

Now, if the function was edited to say:
``` python
// myutils.generic
def testfunction(a, b):
    pass
```
It would have to be **re-imported** by using:
``` python
import importlib
importlib.reload(generic)
help(testfunction)
```
which *should* print something like:
> Help on function testfunction in module myutils.generic:
> testfunction(a, b)
# Guide 📔

- Navigate sample historical horse racing and greyhound racing markets from the Betfair Exchange.

- Visualise historic odds information for each runner leading up to the start of the race. 
  - Changes in odds are caused by users betting *backing* and *laying* selections
  
  - This is analogous to *buying* and *selling* shares on the stock market.

- The stages of workflow through the tabs is provided below. 

- To navigate to a tab, select from the navigation bar on the left hand side

![image-20210914151412171](https://i.loli.net/2021/09/14/FmqpkKnzDu358hI.png)

## 1. Strategy 🎯 (optional)

- Sample strategies are provided where an algorithm is back-tested to see if it is profitable.

- Strategies are simulated on historic markets as if they were running live
  - The total number of markets is indicated by column *Market Count* 
  
  - The total profit from the strategy is indicated by column *Total Profit*

- To download a strategy to the **Markets** tab and view the profit of a given strategy for each market it was simulated on: 

  1. Navigate to the **Strategies** tab
  
  2. Select a cell from the row of the desired strategy

  3. Click the download button

  4. Navigate to the **Markets** tab

![image-20210914151729105](https://i.loli.net/2021/09/14/eX6QoskPNOcYEMx.png)

## 2. Markets 🛒

- Navigate through historical betting markets and select the market desired for further analysis

  > If a strategy has been downloaded, the *Profit* tab will contain total simulated profit from that market - if not the *Profit* tab will be blank

- To download a market to the **Runners** tab and view information on individual runners:

  1. Navigate to the **Markets** tab
  2. Select a cell from the desired row of the market to analyse
  3. Click the *Download* button
  4. Navigate to the **Runners** tab

![image-20210914152430851](https://i.loli.net/2021/09/14/59y6EcMKdnaXWge.png)

## 3. Runners 🏃

- Navigate participating runners of a historic market, sorted by the shortest odds (known as the favourite) to the longest odds (least likely to win.)

  > If the market is downloaded to the **Runners** tab with a strategy selected, the *Profit* tab will contain the simulated profit from trading that runner - if not, the *Profit* tab will be blank

- To plot a figure for a selected runner and add it to the **Figures** tab:

  1. Navigate to the **Runners** tab
  
  2. Select a cell from the desired row of the runner to plot
  
  3. Select the configuration for plotting (if left blank the default is to plot the best back, lay and last traded price)
  
  4. Click the *Figure* button

  5. Navigate to the **Figures** tab

- To select a custom configuration for a figure:

  1. Click the options (**≡**) icon
  
  2. (Optional) Select a custom plot configuration (e.g. *smooth*)
  
  3. (Optional) Select the amount of time prior to the race start to plot (*the higher this is the longer it will take to generate the figure*)
  
  4. Click the *Figure* button

![image-20210914164551623](https://i.loli.net/2021/09/14/QjFL97pkVAIEsMH.png)

### 3.1 Figures 📈

- On successful plot of a figure from the **Runners** tab, a figure will be added to the **Figures** tab.

- All plotted figures are indexed numerically and can be selected, or removed using the *Delete figure* button

  > Figures are stored in the browser, so the more figures plotted the more will be consumed by the browser

![image-20210914164107649](https://i.loli.net/2021/09/14/LQjpVNIxzFUMylb.png)

### 3.2 Orders 💰

- Clicking the *Orders* button whilst on the **Runners** tab will output a list of traded orders with profit to the **Orders** tab if:

  1. A strategy has been selected when downloading to the **Runners** tab

  2. A runner is selected


### 3.3 Timings 🕒

On successful generation of a figure from the **Runners** tab, the timings to create each feature will be logged to 
a table in the **Timings** tab

  > Features are nested, meaning entries with smaller *Level*s in the table have "sub" features and whose timings will include all "sub" features

## 4. Logger 📝

- All notifications that appear in the bottom-left corner of the screen during interactions with the tool are logged to the **Logger** tab

 
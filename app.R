# app.R ---------------------------------------------------------------
# Entry point. Run this file (e.g. click "Run App" in RStudio, or
# shiny::runApp()) to start the buyer's furniture shop app.

library(shiny)
library(shinymanager)

source("R/db.R")
source("R/auth.R")
source("R/ui.R")
source("R/server.R")

dir.create("data", showWarnings = FALSE)

init_credentials_db()

setup_con <- get_shop_con()
init_shop_db(setup_con)
dbDisconnect(setup_con)

ui <- secure_app(app_ui)

shinyApp(ui = ui, server = app_server)

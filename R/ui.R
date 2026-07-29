# ui.R --------------------------------------------------------------
# What the buyer sees: a budget summary, the catalogue, an order form,
# and a list of their past orders. Login itself is handled by
# shinymanager::secure_app() in app.R, not here.

library(shiny)

app_ui <- fluidPage(
  title = "Furniture Shop",
  tags$head(
    tags$style(HTML("
      .swatch { display: inline-block; width: 28px; height: 28px;
                border-radius: 4px; vertical-align: middle; }
      .budget-box { padding: 12px 16px; border-radius: 6px; background: #f2f2f2;
                    margin-bottom: 16px; font-size: 1.1em; }
      .budget-box.over { background: #fbeaea; color: #a33; }
    "))
  ),

  titlePanel("Furniture Shop"),
  uiOutput("budget_summary"),

  tabsetPanel(
    tabPanel(
      "Catalogue",
      br(),
      fluidRow(
        column(7, tableOutput("catalogue_table")),
        column(
          5,
          wellPanel(
            h4("Place an order"),
            selectInput("product_id", "Product", choices = NULL),
            numericInput("quantity", "Quantity", value = 1, min = 1, step = 1),
            actionButton("place_order", "Place order", class = "btn-primary"),
            br(), br(),
            textOutput("order_message")
          )
        )
      )
    ),
    tabPanel(
      "My Orders",
      br(),
      tableOutput("orders_table")
    )
  )
)

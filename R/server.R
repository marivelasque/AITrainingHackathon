# server.R ----------------------------------------------------------
# App logic: who's logged in, what's in the catalogue, placing orders,
# and keeping the budget display up to date.

library(shiny)
library(shinymanager)

app_server <- function(input, output, session) {
  res_auth <- secure_server(check_credentials = shop_check_credentials())

  con <- get_shop_con()
  onSessionEnded(function() dbDisconnect(con))

  products <- get_products(con)
  updateSelectInput(
    session, "product_id",
    choices = setNames(
      products$id,
      sprintf("%s - $%.2f", products$name, products$price)
    )
  )

  username <- reactive(res_auth$user)
  budget   <- reactive(as.numeric(res_auth$budget))

  # Bumped after every successful order so spend/orders re-read from the db.
  orders_version <- reactiveVal(0)

  spent <- reactive({
    orders_version()
    get_spent(con, username())
  })

  output$budget_summary <- renderUI({
    req(username())
    remaining <- budget() - spent()
    div(
      class = if (remaining < 0) "budget-box over" else "budget-box",
      sprintf(
        "Logged in as %s — Budget: $%.2f | Spent: $%.2f | Remaining: $%.2f",
        username(), budget(), spent(), remaining
      )
    )
  })

  output$catalogue_table <- renderTable(
    {
      display <- products
      display$Swatch <- sprintf(
        '<span class="swatch" style="background:%s;"></span>', display$colour
      )
      display$price <- sprintf("%.2f", display$price)
      display[, c("Swatch", "name", "category", "price", "description")] |>
        setNames(c("", "Name", "Category", "Price ($)", "Description"))
    },
    sanitize.text.function = function(x) x,
    striped = TRUE
  )

  order_message <- reactiveVal("")

  observeEvent(input$place_order, {
    req(input$product_id)
    result <- place_order(
      con, username(), as.integer(input$product_id), input$quantity, budget()
    )
    order_message(result$message)
    if (result$success) orders_version(orders_version() + 1)
  })

  output$order_message <- renderText(order_message())

  output$orders_table <- renderTable({
    orders_version()
    df <- get_orders(con, username())
    if (nrow(df) == 0) {
      return(data.frame(Message = "No orders yet."))
    }
    df <- df[, c("ordered_at", "product_name", "quantity", "unit_price", "order_total")]
    df$unit_price  <- sprintf("%.2f", df$unit_price)
    df$order_total <- sprintf("%.2f", df$order_total)
    setNames(df, c("Ordered at", "Product", "Qty", "Unit price ($)", "Total ($)"))
  })
}

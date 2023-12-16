// requires jQuery

function acceptOrder(order_id) {
    console.log("Accepting order: " + order_id);
    $.ajax({
        type: "POST",
        url: "/accept_order",
        contentType: "application/json",
        data: JSON.stringify({ order_id: order_id }),
        dataType: "json",
        success: function (response) {
            console.log(response);
            window.location.href = "/driver_ongoing_ride/" + order_id;
        },
        error: function (err) {
            console.log(err);
        }
    });
};
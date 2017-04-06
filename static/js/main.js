$('.trigger').popover({
    container: 'body',
    html: true,
    title: function () {
        return $('#head-popover-markup').html();
    },
    content: function () {
        return $('#content-popover-markup').html();
    }
});
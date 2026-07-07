PR_SEARCH = """
query($q:String!, $cursor:String) {
  search(query:$q, type:ISSUE, first:50, after:$cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        databaseId number state body
        createdAt mergedAt
        author { login __typename }
        additions deletions changedFiles
        comments { totalCount }
        reviewThreads { totalCount }
      }
    }
  }
}"""

PR_COMMENTS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequest(number:$pr){
      comments(first:50,after:$cursor){
        pageInfo{ hasNextPage endCursor }
        nodes{
          databaseId body createdAt
          author{ login __typename }
        }
      }
    }
  }
}"""

REVIEW_THREADS = """
query($owner:String!,$name:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequest(number:$pr){
      reviewThreads(first:30,after:$cursor){
        pageInfo{ hasNextPage endCursor }
        nodes{
          id
          comments(first:20){
            nodes{
              databaseId body createdAt
              author{ login __typename }
            }
          }
        }
      }
    }
  }
}"""